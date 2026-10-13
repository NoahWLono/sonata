"""Deterministic runtime sonification, expressed in quarter-note beats.

Source lines supply recurring motifs, values move within a scale, arrays are
arpeggios, call depth changes register/voice, and control flow adds cadences.
Every event owns at least one note; no random state or audio assets are used.
"""

from __future__ import annotations

import math
import hashlib
from collections.abc import Iterable, Mapping

from .profiles import event_selected, validate_profile


PALETTES = {
    "classical": {"root": 60, "scale": (0, 2, 4, 5, 7, 9, 11), "gate": 0.88,
                  "velocity": 78, "programs": (0, 40, 42, 73)},
    "electronic": {"root": 48, "scale": (0, 2, 3, 5, 7, 8, 10), "gate": 0.72,
                   "velocity": 94, "programs": (80, 81, 38, 10)},
    "ambient": {"root": 60, "scale": (0, 2, 4, 7, 9), "gate": 2.4,
                "velocity": 64, "programs": (89, 88, 91, 11)},
}
EVENT_STRIDE = 0.25
MAX_NOTES = 100_000


def palette_config(palette: str) -> dict:
    """Resolve a named palette, rejecting misspellings explicitly."""
    if palette not in PALETTES:
        raise ValueError(f"Unknown palette {palette!r}; choose {', '.join(PALETTES)}")
    return PALETTES[palette]


def validate_bpm(bpm: float) -> float:
    value = float(bpm)
    if not math.isfinite(value) or not 4 <= value <= 1000:
        raise ValueError("bpm must be finite and between 4 and 1000")
    return value


def validated_notes(notes: Iterable[Mapping]) -> list[dict]:
    """Validate the symbolic export boundary without clipping or dropping notes."""
    result = []
    for index, source in enumerate(notes):
        if index >= MAX_NOTES:
            raise ValueError(f"Note limit exceeded ({MAX_NOTES})")
        note = dict(source)
        for name, low, high, default in (("pitch", 0, 127, None),
                                         ("velocity", 1, 127, 90),
                                         ("channel", 0, 15, 0)):
            value = note.get(name, default)
            if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                raise ValueError(f"Note {index}: {name} must be an integer in {low}..{high}")
            note[name] = value
        for name in ("start", "duration"):
            try:
                value = float(note[name])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"Note {index}: {name} must be a finite number") from exc
            if not math.isfinite(value) or value < 0 or (name == "duration" and value == 0):
                raise ValueError(f"Note {index}: {name} must be finite and {'positive' if name == 'duration' else 'nonnegative'}")
            note[name] = value
        if not math.isfinite(note["start"] + note["duration"]):
            raise ValueError(f"Note {index}: end time must be finite")
        result.append(note)
    return result


def _value_degree(value: object) -> int:
    if isinstance(value, bool):
        return 4 if value else 0
    if isinstance(value, int):
        return value % 21
    if isinstance(value, float):
        return math.floor(value) % 21 if math.isfinite(value) else 0
    if isinstance(value, (str, list, tuple, dict)):
        return len(value) % 21
    return 0


def sonify(trace: Iterable[Mapping], palette: str = "classical", profile=None) -> list[dict]:
    """Convert ordered execution events to linked, reproducible musical notes.

    An event advances the clock by 0.25 beats. Each array member gets a note
    evenly spaced inside that slot. Ambient notes sustain across slots.
    A repeated pitch on the same channel releases at the next onset, avoiding
    MIDI's ambiguous overlapping unisons. Other ambient pitches keep sustaining.
    Channel 10 (index 9) is avoided because General MIDI reserves it for drums.
    """
    config = palette_config(palette)
    settings = validate_profile(profile)
    stride = settings["event_stride"]
    scale = config["scale"]
    channels = (0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15)
    notes = []
    previous_variables = {}
    for step, event in enumerate(trace):
        if step >= 100_000:
            raise ValueError("Trace event limit exceeded (100000)")
        selected = event_selected(event, previous_variables, settings)
        previous_variables = event.get("variables") or {}
        if not selected:
            continue
        event_id = event.get("id", step)
        line = int(event.get("line", 1))
        depth = max(0, int(event.get("depth", 0)))
        kind = event.get("kind", "statement")
        data = event.get("data") or {}
        value = data.get("value")
        values = list(value) if isinstance(value, (list, tuple)) and value else [value]
        slot = stride / len(values)
        if profile is not None and slot < 1 / 30_720:
            raise ValueError("event_stride is too short for this array at MIDI resolution; increase event_stride")
        motif = (max(1, line) - 1) % len(scale)
        if settings["mapping"] == "semantic":
            identity = "\x1f".join(str(part) for part in (
                event.get("function", "<main>"), kind, data.get("name", ""),
                data.get("statement", ""), data.get("operator", "")))
            motif = int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:4], "big") % len(scale)
        if kind in {"call", "return"}:
            name = str(data.get("name") or event.get("function") or "main")
            # Letters contribute alphabet positions, weighted by their place.
            # This phrase is stable across call sites and Python processes.
            motif = sum((index + 1) * (ord(letter.lower()) - 96)
                        for index, letter in enumerate(name)) % (2 * len(scale))
        base = config["root"] + (depth % 3 - 1) * 12
        voice = depth % len(channels)
        for member, item in enumerate(values):
            degree = motif + _value_degree(item)
            cue = None
            bounds = settings["ranges"].get(data.get("name"), settings["ranges"].get("*"))
            if bounds is not None and type(item) is int:
                low, high = bounds
                degree = motif + (max(low, min(high, item)) - low) * (2 * len(scale)-1) // (high-low)
                cue = "below_range" if item < low else "above_range" if item > high else None
            pitch = base + scale[degree % len(scale)] + 12 * ((degree // len(scale)) % 2)
            if bounds is not None and type(item) is int:
                pitch = base + scale[degree % len(scale)] + 12 * (degree // len(scale))
            accent = 0
            harmony = []
            if kind == "branch":
                taken = data.get("taken", bool(value))
                pitch = base + (7 if taken else 2)
                harmony = [pitch + (5 if taken else 3)]
                accent = 10
            elif kind == "call":
                harmony = [pitch + 7]
                accent = 8
            elif kind == "return":
                pitch = base + scale[motif % len(scale)] + 12 * (motif // len(scale))
                harmony = [pitch + 7, pitch + 12]
            elif kind == "error":
                harmony = [pitch + 1, pitch + 6]
                accent = 25
            elif kind == "output":
                accent = 12
            elif kind == "loop":
                accent = int(data.get("iteration", 0)) % 4 * 3
            sounding = [(p, None) for p in dict.fromkeys([pitch, *harmony])]
            if cue:
                cue_pitch = pitch + (1 if cue == "above_range" else -1)
                sounding = [(p, label) for p, label in sounding if p != cue_pitch]
                sounding.append((cue_pitch, cue))
            for sounding_pitch, cue_name in sounding:
                if len(notes) >= MAX_NOTES:
                    raise ValueError(f"Note limit exceeded ({MAX_NOTES})")
                notes.append({
                    "id": len(notes), "event_id": event_id, "line": line,
                    "start": step * stride + member * slot,
                    "duration": max(1 / 480, slot * config["gate"]),
                    "pitch": max(0, min(127, sounding_pitch)),
                    "velocity": min(127, config["velocity"] + accent),
                    "channel": channels[voice], "voice": voice,
                })
                if profile is not None:
                    notes[-1]["trace_index"] = step
                if cue_name:
                    notes[-1]["cue"] = cue_name
    previous = {}
    for note in notes:
        key = (note["channel"], note["pitch"])
        prior = previous.get(key)
        if prior is not None and prior["start"] + prior["duration"] > note["start"]:
            prior["duration"] = note["start"] - prior["start"]
        previous[key] = note
    return notes
