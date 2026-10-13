"""Optional real-time MIDI ports and bounded, replayable channel recordings.

Hardware is accessed only by explicit port-opening calls. Importing this module
requires Mido, already a core dependency, but never imports the native backend.
"""

from io import BytesIO
import math
import time

import mido

from .midi_guard import checked_midi_bytes


MAX_MESSAGES = 100_000
MAX_SECONDS = 300
_CHANNEL_TYPES = {"note_on", "note_off", "control_change", "program_change",
                  "pitchwheel", "aftertouch", "polytouch"}


def _backend():
    try:
        import rtmidi  # noqa: F401; imported only after an explicit I/O request.
    except ImportError as exc:
        raise RuntimeError("Live MIDI needs the optional dependency: pip install 'sonata-lang[midi]'") from exc
    return mido.Backend("mido.backends.rtmidi")


def list_ports():
    backend = _backend()
    return {"inputs": backend.get_input_names(), "outputs": backend.get_output_names()}


def _message(value):
    if type(value) is not dict or type(value.get("type")) is not str or value["type"] not in _CHANNEL_TYPES:
        raise ValueError("Recording supports MIDI channel messages only (no SysEx or system messages)")
    if any(type(item) is not int for key, item in value.items() if key != "type"):
        raise ValueError("MIDI message fields must be integers")
    if "time" in value:
        raise ValueError("Message time belongs in time_us, not the MIDI payload")
    try:
        result = mido.Message.from_dict(value)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"Invalid MIDI channel message: {exc}") from exc
    return result


def _payload(message):
    value = message.dict()
    value.pop("time", None)
    return value


def validate_recording(recording):
    """Validate and copy schema v1, with integer microsecond timestamps."""
    fields = {"schema", "version", "duration_us", "messages", "ignored_messages"}
    if type(recording) is not dict or set(recording)-fields:
        raise ValueError("MIDI recording must be a schema-v1 object")
    if recording.get("schema") != "sonata-midi-recording" or type(recording.get("version")) is not int or recording["version"] != 1:
        raise ValueError("Unsupported MIDI recording schema/version")
    duration = recording.get("duration_us")
    if type(duration) is not int or not 0 <= duration <= MAX_SECONDS * 1_000_000:
        raise ValueError("Recording duration_us must be in 0..300000000")
    messages = recording.get("messages")
    if type(messages) is not list or len(messages) > MAX_MESSAGES:
        raise ValueError("MIDI message limit exceeded or messages is not a list")
    ignored = recording.get("ignored_messages", 0)
    if type(ignored) is not int or not 0 <= ignored <= MAX_MESSAGES:
        raise ValueError("Invalid ignored_messages count")
    result = {"schema": "sonata-midi-recording", "version": 1, "duration_us": duration,
              "messages": [], "ignored_messages": ignored}
    previous = 0
    for item in messages:
        if type(item) is not dict or set(item) != {"time_us", "message"}:
            raise ValueError("Recorded event needs time_us and message")
        stamp = item["time_us"]
        if type(stamp) is not int or not previous <= stamp <= duration:
            raise ValueError("Message times must be monotone integer microseconds within the recording")
        previous = stamp
        result["messages"].append({"time_us": stamp, "message": _payload(_message(item["message"]))})
    return result


def _speed(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not .1 <= value <= 10:
        raise ValueError("Playback speed must be finite and in 0.1..10")
    return float(value)


def recording_inputs(recording, max_notes=256):
    """Convert sounding note-on messages to [pitches, velocities, times_us].

    The three integer arrays are ordinary SONATA input fixtures. Channels and
    controls remain in the original recording but are not part of this adapter.
    No message is silently truncated when the configured array limit is reached.
    """
    if type(max_notes) is not int or not 0 <= max_notes <= 4096:
        raise ValueError("max_notes must be an integer in 0..4096")
    recording = validate_recording(recording)
    pitches, velocities, times = [], [], []
    for event in recording["messages"]:
        message = event["message"]
        if message["type"] == "note_on" and message["velocity"] > 0:
            if len(pitches) >= max_notes:
                raise ValueError("Recorded note input limit exceeded")
            pitches.append(message["note"])
            velocities.append(message["velocity"])
            times.append(event["time_us"])
    return [pitches, velocities, times]


def _cleanup(port):
    # Both messages are attempted even if the device disappears during reset.
    try:
        port.reset()
    finally:
        port.panic()


def replay_midi(recording, port_name=None, speed=1, *, port=None,
                clock=time.monotonic, sleep=time.sleep, stop=None):
    """Replay a captured stream on an absolute schedule; always release notes.

    `stop` is an optional zero-argument cancellation predicate. Clock and port
    injection support deterministic tests without opening hardware. Caller-
    supplied ports remain open; ports opened here are closed in all cases.
    """
    recording, speed = validate_recording(recording), _speed(speed)
    owned = port is None
    if owned:
        if not isinstance(port_name, str) or not port_name:
            raise ValueError("Choose an output port explicitly")
        port = _backend().open_output(port_name)
    sent, stopped, started = 0, False, clock()

    def wait(until):
        while True:
            if stop is not None and stop():
                return False
            remaining = until - clock()
            if remaining <= 0:
                return True
            sleep(min(remaining, .01))

    try:
        for event in recording["messages"]:
            if not wait(started + event["time_us"] / 1_000_000 / speed):
                stopped = True
                break
            port.send(_message(event["message"]))
            sent += 1
        if not stopped:
            stopped = not wait(started + recording["duration_us"] / 1_000_000 / speed)
    finally:
        try:
            _cleanup(port)
        finally:
            if owned:
                port.close()
    return {"version": 1, "sent_messages": sent, "stopped": stopped,
            "scheduled_seconds": recording["duration_us"] / 1_000_000 / speed}


def capture_midi(port_name=None, seconds=10, max_messages=MAX_MESSAGES, *, port=None,
                 clock=time.monotonic, sleep=time.sleep, stop=None):
    """Record incoming channel messages using the receiver's monotonic clock.

    Other MIDI messages are counted and ignored; the total receive budget also
    counts ignored messages. Input sampling adds OS/backend jitter and polling
    latency. Integer timestamps make subsequent symbolic replay deterministic.
    """
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= MAX_SECONDS:
        raise ValueError("Capture seconds must be finite and in 0..300")
    if type(max_messages) is not int or not 1 <= max_messages <= MAX_MESSAGES:
        raise ValueError("max_messages must be an integer in 1..100000")
    owned = port is None
    if owned:
        if not isinstance(port_name, str) or not port_name:
            raise ValueError("Choose an input port explicitly")
        port = _backend().open_input(port_name)
    started = clock()
    result = {"schema": "sonata-midi-recording", "version": 1, "duration_us": 0,
              "messages": [], "ignored_messages": 0}
    received = 0
    try:
        done = False
        while clock() - started < seconds and not done:
            if stop is not None and stop():
                break
            for message in port.iter_pending():
                stamp = clock() - started
                if stamp > seconds or (stop is not None and stop()):
                    done = True
                    break
                received += 1
                if received > max_messages:
                    raise ValueError("Capture message limit exceeded")
                if message.type not in _CHANNEL_TYPES:
                    result["ignored_messages"] += 1
                    continue
                result["messages"].append({"time_us": round(stamp * 1_000_000), "message": _payload(message)})
            if not done:
                sleep(min(.002, max(0, seconds - (clock()-started))))
        result["duration_us"] = round(min(seconds, clock()-started) * 1_000_000)
    finally:
        if owned:
            port.close()
    return validate_recording(result)


def play_midi(path, port_name=None, speed=1, **kwargs):
    """Play a bounded synchronous MIDI file, respecting its tempo map."""
    midi = mido.MidiFile(file=BytesIO(checked_midi_bytes(path)))
    if midi.type == 2 or midi.ticks_per_beat <= 0:
        raise ValueError("Only synchronous beat-timed MIDI files are supported")
    recording = {"schema": "sonata-midi-recording", "version": 1, "duration_us": 0, "messages": []}
    elapsed = 0
    for message in midi:
        elapsed += message.time
        if elapsed > MAX_SECONDS:
            raise ValueError("MIDI playback duration limit exceeded (300 seconds)")
        if message.is_meta:
            continue
        if len(recording["messages"]) >= MAX_MESSAGES:
            raise ValueError("MIDI playback message limit exceeded")
        recording["messages"].append({"time_us": round(elapsed * 1_000_000), "message": _payload(message)})
    recording["duration_us"] = round(elapsed * 1_000_000)
    return replay_midi(recording, port_name, speed, **kwargs)
