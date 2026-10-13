"""Optional native RtMidi verification using only a temporary virtual port."""
import json
import os
from pathlib import Path
import threading
import time

import mido

from sonata.ports import capture_midi, recording_inputs, replay_midi
from sonata.language import parse
from sonata.runtime import execute


def main():
    backend = mido.Backend("mido.backends.rtmidi")
    label = f"SONATA verification {os.getpid()}"
    with backend.open_input(label, virtual=True) as receiving:
        candidates = [name for name in backend.get_output_names() if label in name]
        if len(candidates) != 1:
            raise RuntimeError("Could not uniquely identify the temporary virtual MIDI port")
        stream = {"schema": "sonata-midi-recording", "version": 1,
                  "duration_us": 120000, "messages": []}
        for index, pitch in enumerate((60, 64, 67)):
            stream["messages"].extend([
                {"time_us": 10000 + index * 30000, "message": {"type": "note_on", "channel": 0, "note": pitch, "velocity": 80}},
                {"time_us": 20000 + index * 30000, "message": {"type": "note_off", "channel": 0, "note": pitch, "velocity": 0}},
            ])
        result, failures, ready = [], [], threading.Event()

        def clock():
            ready.set()
            return time.monotonic()

        def capture():
            try:
                result.append(capture_midi(port=receiving, seconds=.5, clock=clock))
            except Exception as error:
                failures.append(str(error))

        worker = threading.Thread(target=capture, daemon=True)
        worker.start()
        if not ready.wait(2):
            raise RuntimeError("Capture failed to start")
        played = replay_midi(stream, candidates[0])
        worker.join(3)
        if worker.is_alive() or failures or not result:
            raise RuntimeError(f"Capture failed: {failures}")
    fixtures = recording_inputs(result[0])
    assert fixtures[0] == [60, 64, 67], fixtures
    assert fixtures[1] == [80, 80, 80], fixtures
    assert fixtures[2] == sorted(fixtures[2])
    program = parse("return sum(input(0));")
    first, second = execute(program, inputs=fixtures), execute(program, inputs=fixtures)
    assert first == second and first["return_value"] == 191
    report = {"passed": True, "backend": "Mido/RtMidi virtual loopback",
              "sent_notes": fixtures[0], "captured_note_count": 3,
              "channel_messages_received": len(result[0]["messages"]),
              "replay": played, "deterministic_fixture_result": 191,
              "scope": "Temporary software port on this Linux host; no physical device or DAW tested. Capture timestamps are measured and may vary."}
    path = Path("docs/verification/midi-loopback.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
