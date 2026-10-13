"""Generate the first acceptance artifacts after its test passes."""
import json
from pathlib import Path

from sonata.audio import render_wav
from sonata.language import parse
from sonata.midi import write_midi
from sonata.music import sonify
from sonata.runtime import execute


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "audio" / "milestone"
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, expected in [("sum", 15), ("off_by_one", 10)]:
        result = execute(parse((root / "examples" / f"{name}.son").read_text()))
        assert result["error"] is None and result["return_value"] == expected
        notes = sonify(result["trace"])
        assert {n["event_id"] for n in notes} == {e["id"] for e in result["trace"]}
        (out / f"{name}.trace.json").write_text(json.dumps(result, indent=2) + "\n")
        (out / f"{name}.notes.json").write_text(json.dumps(notes, indent=2) + "\n")
        write_midi(notes, out / f"{name}.mid")
        metrics = render_wav(notes, out / f"{name}.wav")
        results[name] = {"result": result["return_value"], "trace_events": len(result["trace"]), "notes": len(notes), "audio": metrics}
    assert results["sum"]["trace_events"] != results["off_by_one"]["trace_events"]
    (out / "acceptance.json").write_text(json.dumps({"passed": True, "runs": results}, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
