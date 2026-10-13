"""Measured mapping and study-design contracts; no participant observations."""
import csv
import math
import wave
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pytest

from experiments.analyze import (
    candidate_notes, decode_candidate, mapping_metrics, signal_metrics,
    first_divergence, perturb_notes,
)
from research.study import assignments, summarize_responses, stimulus_catalog, RESPONSE_FIELDS


def events():
    return [
        {"id": 0, "kind": "assign", "line": 1, "col": 1, "depth": 0, "data": {"value": 1}},
        {"id": 1, "kind": "assign", "line": 8, "col": 1, "depth": 0, "data": {"value": 22}},
        {"id": 2, "kind": "return", "line": 9, "col": 1, "depth": 0, "data": {"value": 22}},
    ]


@pytest.mark.parametrize("mapping", ["A", "B"])
def test_candidate_kind_is_recovered_but_event_identity_collides(mapping):
    trace = events()
    notes = candidate_notes(trace, mapping)
    # Recovery has no trace IDs or source-location metadata available.
    bare = [{k: n[k] for k in ("pitch", "start", "duration", "velocity", "channel")} for n in notes]
    assert decode_candidate(bare, mapping) == ["assign", "assign", "return"]
    measured = mapping_metrics(trace, notes)
    assert measured["event_count"] == 3
    assert measured["unique_event_identities"] == 3
    assert measured["unique_note_signatures"] == 2
    assert measured["identity_collision_groups"] == 1


def test_symbolic_tempo_preserves_kind_while_coarse_rhythm_quantization_loses_it():
    score = candidate_notes(events(), "B")
    slower = [{**n, "start": n["start"] * 2, "duration": n["duration"] * 2} for n in score]
    assert decode_candidate(slower, "B", time_scale=2) == ["assign", "assign", "return"]
    damaged = perturb_notes(score, grid=1)
    assert decode_candidate(damaged, "B") != ["assign", "assign", "return"]


def test_polyphonic_mapping_has_explicit_value_and_location_collision():
    from sonata.music import sonify
    measured = mapping_metrics(events(), sonify(events()))
    assert measured["identity_collision_groups"] == 1
    assert measured["events_in_identity_collision_groups"] == 2


def test_divergence_reports_first_difference_and_length_only_changes():
    assert first_divergence([1, 2], [1, 3]) == 1
    assert first_divergence([1], [1, 2]) == 1
    assert first_divergence([1], [1]) is None


def test_signal_metrics_measure_real_pcm(tmp_path):
    path = tmp_path / "tone.wav"
    samples = np.rint(0.5 * 32767 * np.sin(2 * np.pi * 1000 * np.arange(8000) / 8000)).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(samples.tobytes())
    result = signal_metrics(path)
    assert result["duration_seconds"] == 1
    assert result["rms_normalized"] == pytest.approx(math.sqrt(0.125), abs=0.001)
    assert result["spectral_centroid_hz"] == pytest.approx(1000, abs=3)


def test_study_counterbalances_conditions_without_repeating_exact_tasks():
    rows = assignments(6)
    assert len(rows) == 90
    for participant in {r["participant_id"] for r in rows}:
        own = [r for r in rows if r["participant_id"] == participant]
        assert len({r["stimulus_id"] for r in own}) == 15
        assert [sum(r["condition"] == c for r in own) for c in "ABC"] == [5, 5, 5]
    for block in (1, 2, 3):
        assert [sum(r["block"] == block and r["condition"] == c for r in rows) for c in "ABC"] == [10, 10, 10]
    for condition in "ABC":
        for variant in range(3):
            own = [r for r in rows if r["condition"] == condition and r["variant"] == variant]
            assert len(own) == 10
            assert sum(r["expected_abnormal"] for r in own) == 5
            for family in {r["task_type"] for r in rows}:
                statuses = [r["expected_abnormal"] for r in own if r["task_type"] == family]
                assert sorted(statuses) == [0, 1]
    catalog = stimulus_catalog()
    assert len(catalog) == 30
    assert len({s["source"] for s in catalog}) == 30
    assert {s["task_type"] for s in catalog} == {"off_by_one", "bounded_loop", "unexpected_recursion", "control_flow", "normal_abnormal"}


def test_no_responses_produces_no_invented_statistics(tmp_path):
    path = tmp_path / "empty.csv"
    with path.open("w", newline="") as stream:
        csv.DictWriter(stream, fieldnames=RESPONSE_FIELDS).writeheader()
    result = summarize_responses(path)
    assert result["observations"] == 0
    assert result["conditions"] == {}
    assert result["participants"] == 0


def test_actual_response_rows_are_validated_and_summarized(tmp_path):
    path = tmp_path / "responses.csv"
    row = dict.fromkeys(RESPONSE_FIELDS, "")
    row.update(participant_id="P001", trial="1", condition="A", stimulus_id="S1",
               expected_abnormal="0", reported_abnormal="1", elapsed_seconds="12",
               confidence="80", programming_years="4", music_years="0", training_seconds="90",
               tlx_mental="40", tlx_physical="0", tlx_temporal="20", tlx_performance="30", tlx_effort="40", tlx_frustration="50")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESPONSE_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    result = summarize_responses(path)
    assert result["conditions"]["A"]["accuracy"] == 0
    assert result["conditions"]["A"]["false_positive_rate"] == 1
    assert result["conditions"]["A"]["median_seconds"] == 12
    assert result["conditions"]["A"]["mean_raw_tlx"] == 30
    row["elapsed_seconds"] = "nan"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESPONSE_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(ValueError):
        summarize_responses(path)


def test_response_duplicate_detection_normalizes_integer_trial_spelling(tmp_path):
    path = tmp_path / "duplicates.csv"
    row = dict.fromkeys(RESPONSE_FIELDS, "0")
    row.update(participant_id="P001", stimulus_id="S1", trial="1", condition="A")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESPONSE_FIELDS)
        writer.writeheader()
        writer.writerow(row)
        writer.writerow({**row, "trial": "1.0"})
    with pytest.raises(ValueError, match="Repeated trial"):
        summarize_responses(path)
