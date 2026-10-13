"""Compare symbolic event mappings and measure rendered PCM recordings."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import wave

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sonata.codec import import_program
from sonata.language import canonical, parse
from sonata.midi import read_midi, write_midi
from sonata.music import sonify

KINDS = ("statement", "declare", "read", "assign", "loop", "branch", "call", "return", "output", "error")
DEMOS = ("sum", "off_by_one", "fibonacci", "bubble_sort", "binary_search", "binary_search_miss", "infinite_recursion")


def candidate_notes(trace, mapping):
    """A: one pitch per kind; B: one duration per kind, fixed 0.5-beat cells."""
    if mapping not in {"A", "B"}:
        raise ValueError("Candidate mapping must be A or B")
    score = []
    for i, event in enumerate(trace):
        code = KINDS.index(event["kind"])
        score.append({"id": i, "event_id": event["id"], "line": event["line"],
                      "pitch": 48 + code * 2 if mapping == "A" else 60,
                      "start": i * 0.5, "duration": 0.25 if mapping == "A" else (code + 1) / 32,
                      "velocity": 80, "channel": 0, "voice": 0})
    return score


def decode_candidate(notes, mapping, *, time_scale=1.0):
    """Recover event kinds using note content only and a supplied tempo scale.

    Unknown symbols produce None. This is exact symbolic decoding, not an
    auditory recognizer, and assumes one note per event in onset order.
    """
    if mapping not in {"A", "B"} or not np.isfinite(time_scale) or time_scale <= 0:
        raise ValueError("Invalid decoder configuration")
    decoded = []
    for note in sorted(notes, key=lambda n: n["start"]):
        raw = (note["pitch"] - 48) / 2 if mapping == "A" else note["duration"] * 32 / time_scale - 1
        code = round(raw)
        decoded.append(KINDS[code] if abs(raw - code) < 1e-7 and 0 <= code < len(KINDS) else None)
    return decoded


def identity(event):
    """Event content, excluding sequence ID, full variable snapshots, and stack."""
    return json.dumps({key: event.get(key) for key in ("kind", "line", "col", "depth", "function", "data")}, sort_keys=True)


def event_signatures(trace, notes):
    """Oracle-linked musical signatures without event IDs, absolute time, or line.

    Linking notes to events uses the trace metadata solely to measure collisions.
    It is not claimed to reconstruct that linkage from a recording.
    """
    by_event = defaultdict(list)
    for note in notes:
        by_event[note["event_id"]].append(note)
    signatures = []
    for event in trace:
        own = by_event[event["id"]]
        start = min((note["start"] for note in own), default=0)
        signatures.append(tuple(sorted(
            (n["pitch"], round(n["start"] - start, 8), round(n["duration"], 8), n["velocity"], n["channel"])
            for n in own)))
    return signatures


def mapping_metrics(trace, notes):
    signatures = event_signatures(trace, notes)
    groups = defaultdict(list)
    for event, signature in zip(trace, signatures):
        groups[signature].append(event)
    collisions = [rows for rows in groups.values() if len({identity(e) for e in rows}) > 1]
    ambiguous = [rows for rows in groups.values() if len({e["kind"] for e in rows}) > 1]
    majority = sum(max(Counter(e["kind"] for e in rows).values()) for rows in groups.values())
    return {
        "event_count": len(trace), "note_count": len(notes),
        "unique_event_identities": len({identity(e) for e in trace}),
        "unique_note_signatures": len(groups),
        "identity_collision_groups": len(collisions),
        "events_in_identity_collision_groups": sum(len(rows) for rows in collisions),
        "kind_collision_groups": len(ambiguous),
        "events_in_kind_collision_groups": sum(len(rows) for rows in ambiguous),
        "oracle_kind_majority_accuracy_on_this_corpus": majority / len(trace) if trace else None,
        "signature_scope": "Per-event note content; IDs, absolute onset, and source location excluded; grouping uses trace IDs",
    }


def perturb_notes(notes, *, grid):
    if not np.isfinite(grid) or grid <= 0:
        raise ValueError("Quantization grid must be finite and positive")
    return [{**n, "start": round(n["start"] / grid) * grid,
             "duration": max(grid, round(n["duration"] / grid) * grid)} for n in notes]


def first_divergence(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    return min(len(left), len(right)) if len(left) != len(right) else None


def signal_metrics(path):
    """RMS, energy, and power-weighted STFT centroid from actual 16-bit PCM."""
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2:
            raise ValueError("Measurement expects 16-bit PCM")
        rate, channels, frames = stream.getframerate(), stream.getnchannels(), stream.getnframes()
        signal = np.frombuffer(stream.readframes(frames), dtype="<i2").astype(np.float64) / 32768
        signal = signal.reshape(-1, channels).mean(axis=1)
    square_sum = float(np.sum(signal ** 2))
    window_size = 2048
    frequencies = np.fft.rfftfreq(window_size, 1 / rate)
    window = np.hanning(window_size)
    numerator = denominator = 0.0
    for start in range(0, len(signal), window_size // 2):
        block = signal[start:start + window_size]
        if len(block) < window_size:
            block = np.pad(block, (0, window_size - len(block)))
        power = np.abs(np.fft.rfft(block * window)) ** 2
        numerator += float(np.dot(frequencies, power))
        denominator += float(power.sum())
    return {"sample_rate": rate, "channels": channels, "frames": frames,
            "duration_seconds": frames / rate,
            "rms_normalized": float(np.sqrt(square_sum / len(signal))) if len(signal) else 0.0,
            "energy_normalized_sample_sum": square_sum,
            "peak_normalized": float(np.max(np.abs(signal))) if len(signal) else 0.0,
            "spectral_centroid_hz": numerator / denominator if denominator else 0.0,
            "spectral_method": "2048-sample Hann, 1024 hop, global power weighting; mono downmix"}


def _recovery(expected, actual):
    correct = sum(a == b for a, b in zip(expected, actual))
    return {"expected_symbols": len(expected), "decoded_symbols": len(actual),
            "correct_symbols": correct, "accuracy": correct / len(expected) if expected else None,
            "exact_sequence": expected == actual}


def run_analysis(root: Path) -> dict:
    """Read built demos, write auditable measurements, and return the report."""
    root = Path(root).resolve()
    output = root / "experiments" / "results"
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "kind": "automated_measurements", "participant_observations": 0,
              "claims": "Symbolic-note recovery and PCM statistics only; no listening or usability results.",
              "demos": {}, "missing_demos": [], "source_codec": {}}
    traces, scores = {}, {}
    for name in DEMOS:
        folder = root / "audio" / "demos" / name
        required = [folder / file for file in ("trace.json", "notes.json", "execution.wav", "code.mid")]
        if not all(path.exists() for path in required):
            report["missing_demos"].append(name)
            continue
        raw = json.loads(required[0].read_text())
        trace = raw["trace"] if isinstance(raw, dict) else raw
        notes = json.loads(required[1].read_text())
        traces[name], scores[name] = trace, notes
        entry = {"input_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in required},
                 "kind_counts": dict(Counter(e["kind"] for e in trace)),
                 "signal": signal_metrics(required[2]), "mappings": {}}
        for mapping in ("A", "B", "C"):
            mapped = notes if mapping == "C" else candidate_notes(trace, mapping)
            result = mapping_metrics(trace, mapped)
            result["information_loss"] = (
                "Kind retained; operands, locations, variables, and call stack omitted."
                if mapping != "C" else
                "Values reduce modulo 21; line motifs repeat by scale length; registers/channels repeat with depth; no general inverse."
            )
            if mapping in {"A", "B"}:
                expected = [e["kind"] for e in trace]
                midi = output / "mapping_scores" / f"{name}_{mapping}.mid"
                write_midi(mapped, midi)
                result["exact_note_recovery"] = _recovery(expected, decode_candidate(mapped, mapping))
                result["midi_roundtrip_recovery"] = _recovery(expected, decode_candidate(read_midi(midi), mapping))
                result["tempo_recovery"] = {}
                for bpm in (60, 180):
                    altered = midi.with_name(f"{name}_{mapping}_{bpm}bpm.mid")
                    write_midi(mapped, altered, bpm=bpm)
                    result["tempo_recovery"][str(bpm)] = _recovery(expected, decode_candidate(read_midi(altered), mapping))
                result["coarse_quantization_recovery"] = _recovery(expected, decode_candidate(perturb_notes(mapped, grid=0.125), mapping))
            else:
                result["matches_current_sonify"] = mapped == sonify(trace)
                damaged = perturb_notes(mapped, grid=0.125)
                result["coarse_quantization_changed_signatures"] = sum(
                    a != b for a, b in zip(event_signatures(trace, mapped), event_signatures(trace, damaged)))
                result["tempo_invariance"] = "Mapping takes beats, not tempo; changing playback tempo leaves its note content unchanged."
            entry["mappings"][mapping] = result
        report["demos"][name] = entry
        source = root / "examples" / f"{name}.son"
        report["source_codec"][name] = {"canonical_ast_equal": canonical(import_program(folder / "code.mid")) == canonical(parse(source.read_text())),
                                          "scope": "SC1 symbolic source grammar, separate from runtime mappings"}
    if "sum" in traces and "off_by_one" in traces:
        a, b = traces["sum"], traces["off_by_one"]
        report["off_by_one"] = {
            "first_event_content_divergence_zero_based": first_divergence([identity(e) for e in a], [identity(e) for e in b]),
            "first_musical_event_divergence_zero_based": first_divergence(event_signatures(a, scores["sum"]), event_signatures(b, scores["off_by_one"])),
            "event_count_difference": len(a) - len(b),
            "note_count_difference": len(scores["sum"]) - len(scores["off_by_one"]),
            "interpretation": "Structural difference measured; blind listener discrimination remains untested."}
    (output / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = run_analysis(args.root)
    print(json.dumps({"measured_demos": len(report["demos"]), "missing_demos": report["missing_demos"]}, indent=2))


if __name__ == "__main__":
    main()
