"""Artifact validation separate from the interpreter, codec and renderer.

The reference evaluator shares the parser but no runtime evaluation logic.
This component measures generated files itself; renderer claims are not evidence.
"""
from collections import Counter
import hashlib
import math
from pathlib import Path
import tempfile
import wave

import numpy as np

from .language import parse, canonical
from .runtime import execute
from .reference import evaluate_reference
from .music import sonify
from .codec import compile_program, import_program
from .midi import write_midi, read_midi, TICKS_PER_BEAT
from .audio import render_wav


def audit_correspondence(source, trace, notes):
    """Audit provenance and time cells without calling the sonifier."""
    ids = {e.get("id") for e in trace}
    lookup = {e.get("id"): e for e in trace}
    locations = {(n["line"], n["col"]) for n in _walk(parse(source))}
    lines = source.splitlines() or [""]
    return {
        "trace_ids_contiguous": [e.get("id") for e in trace] == list(range(len(trace))),
        "trace_locations_valid": all((e.get("line"), e.get("col")) in locations and 1 <= e.get("line", 0) <= len(lines) for e in trace),
        "stack_depth_consistent": all(e.get("depth") == len(e.get("stack", [])) - 1 and e.get("function") == e["stack"][-1] for e in trace),
        "every_event_audible": {n.get("event_id") for n in notes} == ids,
        "note_locations_match": all(n.get("event_id") in lookup and n.get("line") == lookup[n["event_id"]]["line"] for n in notes),
        "note_time_cells_match": all(n.get("event_id") in ids and n["event_id"] * .25 <= n["start"] < (n["event_id"] + 1) * .25 for n in notes),
    }


def _walk(node):
    if isinstance(node, dict):
        if "kind" in node:
            yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _behavior(result):
    return {k: result[k] for k in ("output", "return_value", "globals")}


def _note_signature(note):
    return (round(note["start"] * TICKS_PER_BEAT), round((note["start"] + note["duration"]) * TICKS_PER_BEAT), note["pitch"], note["velocity"], note["channel"])


def verify(source, limits=None, inputs=None):
    ast = parse(source)
    result = execute(ast, limits, inputs=inputs)
    expected = evaluate_reference(source, inputs=inputs)
    notes = sonify(result["trace"])
    checks = audit_correspondence(source, result["trace"], notes)
    # Independent semantics are checked for terminating, error-free programs.
    checks["reference_success"] = expected["error"] is None and result["error"] is None
    checks["reference_behavior_matches"] = _behavior(result) == _behavior(expected)
    with tempfile.TemporaryDirectory(prefix="sonata-verify-") as directory:
        path = Path(directory)
        code_notes = compile_program(ast, path / "code.mid")
        compile_program(ast, path / "code-repeat.mid")
        restored = import_program(path / "code.mid")
        restored_run = execute(restored, limits, inputs=inputs)
        checks["canonical_ast_roundtrip"] = canonical(ast) == canonical(restored)
        checks["roundtrip_behavior"] = _behavior(result) == _behavior(restored_run) and (result["error"] or {}).get("kind") == (restored_run["error"] or {}).get("kind")
        checks["deterministic_code_midi"] = (path / "code.mid").read_bytes() == (path / "code-repeat.mid").read_bytes()
        write_midi(notes, path / "execution.mid")
        midi_notes = read_midi(path / "execution.mid")
        checks["runtime_midi_notes_preserved"] = Counter(map(_note_signature, notes)) == Counter(map(_note_signature, midi_notes))
        render_wav(notes, path / "execution.wav")
        with wave.open(str(path / "execution.wav")) as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            samples = np.frombuffer(wav.readframes(frames), dtype="<i2").astype(float) / 32768
        duration = frames / rate
        rms = float(np.sqrt(np.mean(samples ** 2)))
        target = max((n["start"] + n["duration"] for n in notes), default=0) * .5 + .2
        checks["wav_duration"] = math.isclose(duration, target, abs_tol=2 / rate)
        checks["wav_non_silent"] = rms > 0 if notes else rms == 0
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if "repeat" not in p.name}
    return {"schema": "sonata-verification-1", "passed": all(checks.values()), "checks": checks,
            "expected": _behavior(expected), "actual": _behavior(result), "runtime_error": result["error"],
            "trace_events": len(result["trace"]), "runtime_notes": len(notes), "code_notes": len(code_notes),
            "audio": {"duration": duration, "rms": rms, "sample_rate": rate}, "sha256": hashes,
            "shared_dependencies": ["Parser and canonical source printer", "Mido for both MIDI writer and reader", "NumPy numerical runtime", "The codec supplies both encoding and decoding; generated and corruption tests supplement this check"],
            "limits": ["Reference comparison covers successful programs; resource-error equivalence is tested separately", "Trace audit verifies source, stack and note correspondence, not every intermediate arithmetic transition", "No human auditory recognition or usefulness is measured"]}
