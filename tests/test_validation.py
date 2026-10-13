from copy import deepcopy

from sonata.language import parse
from sonata.runtime import execute
from sonata.music import sonify
from sonata.validation import verify, audit_correspondence


def test_complete_independent_report():
    report = verify("let total = 0; for i in 1..6 { total = total + i; } print(total); return total;")
    assert report["passed"]
    assert report["expected"]["return_value"] == 15
    assert all(report["checks"].values())
    assert "parser" in " ".join(report["shared_dependencies"]).lower()


def test_corrupted_note_provenance_is_rejected():
    source = "let x = 1; return x;"
    trace = execute(parse(source))["trace"]
    notes = sonify(trace)
    assert all(audit_correspondence(source, trace, notes).values())
    changed = deepcopy(notes)
    changed[0]["event_id"] = 999
    assert not all(audit_correspondence(source, trace, changed).values())


def test_missing_note_and_invalid_trace_location_are_rejected():
    source = "return 3;"
    trace = execute(parse(source))["trace"]
    notes = sonify(trace)
    assert not all(audit_correspondence(source, trace, notes[1:]).values())
    bad = deepcopy(trace)
    bad[0]["line"] = 500
    assert not all(audit_correspondence(source, bad, notes).values())
