"""Standard MIDI note I/O, with musical time measured in quarter-note beats."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from io import BytesIO

import mido

from .music import MAX_NOTES, palette_config, validate_bpm, validated_notes
from .midi_guard import checked_midi_bytes


TICKS_PER_BEAT = 30_720


def write_midi(notes, path, bpm: float = 120, palette: str = "classical") -> None:
    """Write type-1 MIDI at 30720 PPQ, quantizing times to the nearest tick.

    Overlapping intervals on the same channel/pitch are rejected because MIDI
    note-off messages cannot identify which of those instances they release.
    """
    config = palette_config(palette)
    tempo = validate_bpm(bpm)
    score = validated_notes(notes)
    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)
    conductor.append(mido.MetaMessage("track_name", name="SONATA conductor"))
    conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo)))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4))
    by_channel = defaultdict(list)
    intervals = defaultdict(list)
    for index, note in enumerate(score):
        start = round(note["start"] * TICKS_PER_BEAT)
        end = max(start + 1, round((note["start"] + note["duration"]) * TICKS_PER_BEAT))
        if end > 0x0FFFFFFF:
            raise ValueError("MIDI duration limit exceeded")
        channel = note["channel"]
        intervals[(channel, note["pitch"])].append((start, end))
        by_channel[channel].append((start, 1, index, mido.Message("note_on", channel=channel,
                                                              note=note["pitch"], velocity=note["velocity"])))
        by_channel[channel].append((end, 0, index, mido.Message("note_off", channel=channel,
                                                             note=note["pitch"], velocity=0)))
    for (channel, pitch), spans in intervals.items():
        previous_end = -1
        for start, end in sorted(spans):
            if start < previous_end:
                raise ValueError(f"Ambiguous overlapping MIDI notes for pitch {pitch}, channel {channel}; separate voices or shorten durations")
            previous_end = end
    for channel, events in sorted(by_channel.items()):
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=f"SONATA voice {channel + 1}"))
        track.append(mido.Message("program_change", channel=channel,
                                  program=config["programs"][channel % len(config["programs"])]))
        previous = 0
        for tick, _, _, message in sorted(events, key=lambda event: event[:3]):
            message.time = tick - previous
            track.append(message)
            previous = tick
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    midi.save(str(output))


def read_midi(path) -> list[dict]:
    """Read note events from synchronous MIDI files, preserving channel/velocity.

    Sustain-controller interpretation belongs to playback; this reads explicit
    note on/off intervals. An unfinished note is rejected instead of dropped.
    """
    midi = mido.MidiFile(file=BytesIO(checked_midi_bytes(path)))
    if midi.type == 2 or midi.ticks_per_beat <= 0:
        raise ValueError("Only synchronous, beat-timed MIDI files are supported")
    active = defaultdict(deque)
    result = []
    tick = 0
    order = 0
    for message in mido.merge_tracks(midi.tracks):
        tick += message.time
        if message.type == "note_on" and message.velocity > 0:
            active[(message.channel, message.note)].append((tick, message.velocity, order))
            order += 1
            if order > MAX_NOTES:
                raise ValueError(f"Note limit exceeded ({MAX_NOTES})")
        elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
            key = (message.channel, message.note)
            if active[key]:
                start, velocity, sequence = active[key].popleft()
                result.append({"pitch": message.note, "channel": message.channel,
                               "velocity": velocity, "start": start / midi.ticks_per_beat,
                               "duration": (tick - start) / midi.ticks_per_beat,
                               "_order": sequence})
    if any(active.values()):
        raise ValueError("MIDI contains unfinished notes")
    result.sort(key=lambda note: (note["start"], note["_order"]))
    for note in result:
        del note["_order"]
    return result
