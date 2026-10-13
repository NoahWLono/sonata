"""Acceptance gate: actual execution drives both recordings."""
import json
import wave
from pathlib import Path

import numpy as np

from sonata.language import parse
from sonata.runtime import execute
from sonata.music import sonify
from sonata.midi import write_midi, read_midi
from sonata.audio import render_wav

ROOT = Path(__file__).resolve().parents[1]


def test_first_acceptance_milestone(tmp_path):
    runs = []
    for name, expected in [("sum", 15), ("off_by_one", 10)]:
        result = execute(parse((ROOT / "examples" / f"{name}.son").read_text()))
        assert result["error"] is None
        assert result["return_value"] == expected
        assert result["output"] == [expected]
        trace = result["trace"]
        assert trace and all(e["line"] > 0 for e in trace)
        notes = sonify(trace)
        assert notes == sonify(trace)
        assert {n["event_id"] for n in notes} == {e["id"] for e in trace}
        assert all(n["line"] == trace[n["event_id"]]["line"] for n in notes)
        (tmp_path / f"{name}.trace.json").write_text(json.dumps(result, indent=2))
        write_midi(notes, tmp_path / f"{name}.mid")
        assert len(read_midi(tmp_path / f"{name}.mid")) == len(notes)
        render_wav(notes, tmp_path / f"{name}.wav")
        with wave.open(str(tmp_path / f"{name}.wav")) as wav:
            assert wav.getnframes() > 0
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
            assert np.sqrt(np.mean(samples.astype(float) ** 2)) > 10
            expected_duration = max(n["start"] + n["duration"] for n in notes) * .5 + .2
            assert abs(wav.getnframes() / wav.getframerate() - expected_duration) < .01
        runs.append((result, notes))
    assert len(runs[0][0]["trace"]) > len(runs[1][0]["trace"])
    assert [(n["start"], n["pitch"]) for n in runs[0][1]] != [(n["start"], n["pitch"]) for n in runs[1][1]]
