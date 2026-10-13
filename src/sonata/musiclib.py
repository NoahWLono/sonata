"""Small deterministic composition helpers, separate from language execution."""

from dataclasses import asdict, dataclass
from fractions import Fraction
import json
from pathlib import Path
import re

import mido

from .audio import render_wav
from .midi import TICKS_PER_BEAT, write_midi
from .music import MAX_NOTES, palette_config, validate_bpm, validated_notes


SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10), "pentatonic": (0, 2, 4, 7, 9),
    "chromatic": tuple(range(12)),
}
CHORDS = {"major": (0, 4, 7), "minor": (0, 3, 7), "diminished": (0, 3, 6),
          "sus4": (0, 5, 7), "dominant7": (0, 4, 7, 10), "major7": (0, 4, 7, 11)}
_SAFE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _safe_name(name):
    return isinstance(name, str) and _SAFE_NAME.fullmatch(name) and name.upper() not in _DEVICE_NAMES


def _pitches(values):
    result = []
    for value in values:
        if len(result) >= MAX_NOTES:
            raise ValueError("Pitch note limit exceeded")
        if type(value) is not int or not 0 <= value <= 127:
            raise ValueError("Pitches must be integer MIDI notes in 0..127")
        result.append(value)
    return result


def scale(root=60, mode="major", octaves=1):
    """Return an ascending scale including the final octave root."""
    if mode not in SCALES or type(octaves) is not int or not 1 <= octaves <= 10 or type(root) is not int:
        raise ValueError("Choose a known mode, integer root, and 1..10 octaves")
    return _pitches([root+12*octave+interval for octave in range(octaves) for interval in SCALES[mode]] + [root+12*octaves])


def chord(root=60, quality="major"):
    if quality not in CHORDS or type(root) is not int:
        raise ValueError("Choose a known chord quality and integer root")
    return _pitches(root + interval for interval in CHORDS[quality])


def beat(value, *, positive=False):
    """Parse exact beat time on the 30720-PPQ grid; reject implicit rounding."""
    if type(value) not in (int, float, str, Fraction):
        raise ValueError("Beat time must be a number, Fraction, or rational string")
    if isinstance(value, str) and not re.fullmatch(r"[0-9]{1,8}(?:/[0-9]{1,8}|\.[0-9]{1,8})?", value):
        raise ValueError("Beat string must be a bounded decimal or rational, such as 1/3")
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Invalid rational beat time") from exc
    if result < 0 or result > 8192 or (positive and result == 0):
        raise ValueError("Beat time must be positive" if positive else "Beat time must be in 0..8192")
    if TICKS_PER_BEAT % result.denominator:
        raise ValueError("Beat time is not exact on the 30720-PPQ MIDI grid")
    return result


def rhythm(durations):
    """Validate positive beat lengths, preserving exact rational values."""
    result = []
    for item in durations:
        if len(result) >= MAX_NOTES:
            raise ValueError("Rhythm note limit exceeded")
        result.append(beat(item, positive=True))
    return result


@dataclass(frozen=True)
class Voice:
    name: str
    channel: int
    program: int


def _set_programs(path, programs):
    score = mido.MidiFile(path)
    for track in score.tracks:
        for message in track:
            if message.type == "program_change" and message.channel in programs:
                message.program = programs[message.channel]
    score.save(path)


def export_stems(notes, directory, bpm=120, palette="classical"):
    """Export each voice to MIDI/WAV, retaining the original global clock.

    The returned manifest identifies the original voice value. Unsafe names
    become ordinal filenames; no trace-controlled text becomes a path.
    """
    score = validated_notes(notes)
    palette_config(palette)
    tempo = validate_bpm(bpm)
    groups = {}
    for note in score:
        voice = note.get("voice", note["channel"])
        if type(voice) not in (int, str):
            raise ValueError("Voice names must be strings or integers")
        groups.setdefault((type(voice).__name__, voice), []).append(note)
    if len(groups) > 64:
        raise ValueError("Stem limit exceeded (64 voices)")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "bpm": tempo, "palette": palette, "voices": []}
    used = set()
    for index, ((_, voice), group) in enumerate(groups.items()):
        name = voice if _safe_name(voice) else f"voice-{index:03d}"
        suffix = 0
        while name.casefold() in used:
            suffix += 1
            name = f"voice-{index:03d}-{suffix}"
        used.add(name.casefold())
        write_midi(group, directory/f"{name}.mid", bpm=tempo, palette=palette)
        stats = render_wav(group, directory/f"{name}.wav", bpm=tempo, palette=palette)
        manifest["voices"].append({"voice": voice, "midi": f"{name}.mid", "wav": f"{name}.wav",
                                    "note_count": len(group), "audio": stats})
    (directory/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


class Score:
    """A bounded, deterministic score with explicit voices and rational time."""

    def __init__(self, bpm=120, palette="classical"):
        self.bpm = validate_bpm(bpm)
        palette_config(palette)
        self.palette, self.voices, self.events = palette, {}, []

    def add_voice(self, name, channel=None, program=0):
        if not _safe_name(name) or name in self.voices:
            raise ValueError("Voice names must be unique safe identifiers up to 64 characters")
        used = {v.channel for v in self.voices.values()}
        if channel is None:
            channel = next((c for c in range(16) if c != 9 and c not in used), None)
        if type(channel) is not int or not 0 <= channel <= 15 or channel in used:
            raise ValueError("Voice needs a unique MIDI channel in 0..15")
        if type(program) is not int or not 0 <= program <= 127:
            raise ValueError("Instrument program must be an integer in 0..127")
        self.voices[name] = Voice(name, channel, program)
        return self

    def note(self, voice, pitch, start=0, duration=1, velocity=90):
        if voice not in self.voices:
            raise ValueError("Declare the voice before scheduling notes")
        if len(self.events) >= MAX_NOTES:
            raise ValueError("Score note limit exceeded")
        _pitches([pitch])
        start, duration = beat(start), beat(duration, positive=True)
        if start + duration > 8192:
            raise ValueError("Score duration limit exceeded")
        if type(velocity) is not int or not 1 <= velocity <= 127:
            raise ValueError("Velocity must be an integer in 1..127")
        self.events.append({"pitch": pitch, "start": start, "duration": duration,
                            "channel": self.voices[voice].channel, "voice": voice, "velocity": velocity})
        return self

    def pattern(self, voice, pitches, durations, start=0, velocity=90):
        pitches, durations = _pitches(pitches), rhythm(durations)
        if len(pitches) != len(durations):
            raise ValueError("Pattern must have one duration per pitch")
        cursor = beat(start)
        for pitch, duration in zip(pitches, durations):
            self.note(voice, pitch, cursor, duration, velocity)
            cursor += duration
        return self

    def notes(self):
        """Return the standard JSON-friendly note representation."""
        return validated_notes(self.events)

    def export(self, directory, stems=True):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        notes = self.notes()
        write_midi(notes, directory/"composition.mid", self.bpm, self.palette)
        programs = {v.channel: v.program for v in self.voices.values()}
        _set_programs(directory/"composition.mid", programs)
        stats = render_wav(notes, directory/"composition.wav", self.bpm, self.palette)
        manifest = {"version": 1, "bpm": self.bpm, "palette": self.palette, "note_count": len(notes),
                    "voices": {name: asdict(voice) for name, voice in self.voices.items()}, "audio": stats}
        if stems:
            manifest["stems"] = export_stems(notes, directory/"stems", self.bpm, self.palette)
            for stem in manifest["stems"]["voices"]:
                _set_programs(directory/"stems"/stem["midi"], programs)
        (directory/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
        return manifest
