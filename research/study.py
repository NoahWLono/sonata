"""Generate counterbalanced local study packets and summarize observed CSV rows."""
from __future__ import annotations

import csv
from collections import defaultdict
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil
import statistics

from sonata.audio import render_wav
from sonata.language import parse
from sonata.music import sonify
from sonata.runtime import Limits, execute

ORDERS = ("ABC", "BCA", "CAB", "ACB", "CBA", "BAC")
FAMILIES = ("off_by_one", "bounded_loop", "unexpected_recursion", "control_flow", "normal_abnormal")
CONDITIONS = {"A": "Source and textual execution log", "B": "Source and audio", "C": "Source, audio, and event timeline"}
TLX = ("tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort", "tlx_frustration")
RESPONSE_FIELDS = (
    "participant_id", "trial", "condition", "stimulus_id", "expected_abnormal", "reported_abnormal",
    "elapsed_seconds", "confidence", "programming_years", "music_years", "training_seconds",
    *TLX, "suspected_line", "explanation", "notes",
)


def stimulus_catalog():
    catalog = []
    for family in FAMILIES:
        for variant in range(3):
            for abnormal in (False, True):
                n = 4 + 2 * variant
                if family == "off_by_one":
                    source = f"let total = 0;\nfor i in 1..{n if abnormal else n+1} {{\n    total = total + i;\n}}\nprint(total);\nreturn total;\n"
                    prompt = f"The program should add integers 1 through {n}, inclusive, print the sum, and return it."
                    expected = n * (n + 1) // 2
                    defect = "The exclusive upper bound omits the final addend."
                    line = 2
                elif family == "bounded_loop":
                    source = f"let i = 0;\nwhile (i < {n}) {{\n    i = i + {0 if abnormal else 1};\n}}\nprint(i);\nreturn i;\n"
                    prompt = f"The program should count from zero to {n} and then stop."
                    expected = n
                    defect = "The counter does not advance; execution reaches the configured step limit."
                    line = 3
                elif family == "unexpected_recursion":
                    n = 2 + variant
                    source = f"fn count(n) {{\n    if (n == 0) {{ return 0; }}\n    return 1 + count(n {'+' if abnormal else '-'} 1);\n}}\nreturn count({n});\n"
                    prompt = f"The function should recurse toward zero and return {n}."
                    expected = n
                    defect = "The recursive argument grows away from its base case, reaching the depth limit."
                    line = 3
                elif family == "control_flow":
                    source = f"let reading = {n+2};\nif (reading {'<' if abnormal else '>='} {n}) {{\n    print(1);\n}} else {{\n    print(0);\n}}\nreturn reading;\n"
                    prompt = f"The program should print 1 when the reading is at least {n}, or 0 otherwise."
                    expected = n + 2
                    defect = "The threshold comparison takes the opposite branch."
                    line = 2
                else:
                    source = f"let values = [{n}, {n+1}, {n+2}];\nlet total = 0;\nfor i in 0..len(values) {{\n    total = total {'-' if abnormal else '+'} values[i];\n}}\nprint(total);\nreturn total;\n"
                    prompt = "The program should print and return the sum of every array element."
                    expected = 3 * n + 3
                    defect = "The accumulator subtracts each value instead of adding it."
                    line = 4
                code = "S" + hashlib.sha256(source.encode()).hexdigest()[:10].upper()
                catalog.append({"stimulus_id": code, "task_type": family, "variant": variant,
                                "abnormal": abnormal, "source": source, "prompt": prompt,
                                "expected_return_if_correct": expected, "expected_line": line if abnormal else None,
                                "answer": defect if abnormal else "Behavior matches the stated task."})
    return catalog


def assignments(participants=6):
    if type(participants) is not int or not 1 <= participants <= 300:
        raise ValueError("participants must be an integer in 1..300")
    lookup = {(s["task_type"], s["variant"], s["abnormal"]): s for s in stimulus_catalog()}
    rows = []
    for p in range(participants):
        for block, condition in enumerate(ORDERS[p % 6]):
            # Parameter variants rotate independently from block order.
            variant = ("ABC".index(condition) + p // 2) % 3
            for offset in range(5):
                family_index = (offset + p + block) % 5
                family = FAMILIES[family_index]
                abnormal = bool((p + family_index + variant) % 2)
                stimulus = lookup[(family, variant, abnormal)]
                rows.append({"participant_id": f"P{p+1:03d}", "trial": block * 5 + offset + 1,
                             "block": block + 1, "condition": condition,
                             "stimulus_id": stimulus["stimulus_id"], "task_type": family,
                             "variant": variant, "expected_abnormal": int(abnormal)})
    return rows


def _write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _packet_html(stimulus, condition, result, notes):
    source = "\n".join(f'<span id="line-{i}">{i:>2}  {html.escape(line)}</span>' for i, line in enumerate(stimulus["source"].splitlines(), 1))
    body = f'<h1>Task {stimulus["stimulus_id"]}</h1><p>{html.escape(stimulus["prompt"])}</p><pre>{source}</pre>'
    if condition == "A":
        log = [{k: e[k] for k in ("id", "kind", "line", "depth", "data")} for e in result["trace"]]
        body += '<h2>Execution log</h2><pre>' + html.escape(json.dumps(log, indent=2)) + '</pre>'
    else:
        body += '<p><audio controls preload="metadata" src="execution.wav"></audio></p>'
    if condition == "C":
        body += '<h2>Event timeline</h2><p>Select an event to highlight its source line. Times use 180 BPM.</p><div class="timeline">'
        for event in result["trace"]:
            body += f'<button onclick="mark({event["line"]})">{event["id"] * .25 / 3:.2f}s · {html.escape(event["kind"])} · line {event["line"]} · depth {event["depth"]}</button>'
        body += '</div><script>function mark(n){document.querySelectorAll("pre span").forEach(e=>e.classList.remove("selected"));const e=document.getElementById("line-"+n);if(e){e.classList.add("selected");e.scrollIntoView({block:"nearest"});}}</script>'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>SONATA study task</title><style>body{font:17px system-ui;max-width:1000px;margin:40px auto;padding:20px;background:#fbfaf5;color:#19242a}pre{background:#eeece2;padding:18px;overflow:auto}pre span{display:block}.selected{background:#ffe092}.timeline{max-height:420px;overflow:auto}button{display:block;margin:4px;padding:8px;width:95%;text-align:left}</style>' + body + '</html>'


def generate_kit(root: Path, participants=6) -> dict:
    """Generate 30 verified stimuli and condition-specific local HTML packets.

    Participant CSV files contain no observations until researchers enter them.
    Files in researcher_only are intentionally not participant-safe.
    """
    root = Path(root).resolve()
    base = root / "research"
    private = base / "researcher_only"
    public = base / "participant"
    private.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    previous = private / "assignments.csv"
    if previous.exists():
        with previous.open(newline="") as stream:
            old_rows = list(csv.DictReader(stream))
        for old in old_rows:
            if not re.fullmatch(r"P[0-9]{3}", old.get("participant_id", "")) or not re.fullmatch(r"S[0-9A-F]{10}", old.get("stimulus_id", "")):
                raise ValueError("Refusing cleanup of an unrecognized generated path")
            trial = int(old["trial"])
            if not 1 <= trial <= 15:
                raise ValueError("Refusing cleanup of an unrecognized generated trial")
            folder = public / old["participant_id"] / f'{trial:02d}_{old["stimulus_id"]}'
            for name in ("index.html", "execution.wav"):
                (folder / name).unlink(missing_ok=True)
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
            (public / old["participant_id"] / "index.html").unlink(missing_ok=True)
    catalog = stimulus_catalog()
    schedule = assignments(participants)
    lookup = {s["stimulus_id"]: s for s in catalog}
    outcomes = {}
    for stimulus in catalog:
        code = stimulus["stimulus_id"]
        folder = private / "stimuli" / code
        folder.mkdir(parents=True, exist_ok=True)
        result = execute(parse(stimulus["source"]), Limits(max_steps=150, max_depth=8))
        if not stimulus["abnormal"] and (result["error"] is not None or result["return_value"] != stimulus["expected_return_if_correct"]):
            raise ValueError(f"Healthy stimulus failed verification: {code}")
        if stimulus["task_type"] == "control_flow":
            if result["output"] != ([0] if stimulus["abnormal"] else [1]):
                raise ValueError(f"Branch stimulus failed verification: {code}")
        elif stimulus["abnormal"] and result["error"] is None and result["return_value"] == stimulus["expected_return_if_correct"]:
            raise ValueError(f"Abnormal stimulus did not differ: {code}")
        notes = sonify(result["trace"])
        (folder / "source.son").write_text(stimulus["source"])
        (folder / "trace.json").write_text(json.dumps(result, indent=2) + "\n")
        render_wav(notes, folder / "execution.wav", bpm=180, sample_rate=11025)
        outcomes[code] = (result, notes)
    for row in schedule:
        stimulus = lookup[row["stimulus_id"]]
        result, notes = outcomes[row["stimulus_id"]]
        folder = public / row["participant_id"] / f'{row["trial"]:02d}_{row["stimulus_id"]}'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(_packet_html(stimulus, row["condition"], result, notes))
        if row["condition"] in {"B", "C"}:
            shutil.copyfile(private / "stimuli" / row["stimulus_id"] / "execution.wav", folder / "execution.wav")
    for participant in sorted({r["participant_id"] for r in schedule}):
        links = [f'<li><a href="{r["trial"]:02d}_{r["stimulus_id"]}/index.html">Task {r["trial"]}</a> · {html.escape(CONDITIONS[r["condition"]])}</li>' for r in schedule if r["participant_id"] == participant]
        (public / participant / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>Study sequence</title><h1>' + participant + '</h1><p>Open one task at a time when instructed. Do not browse other task folders.</p><ol>' + ''.join(links) + '</ol>')
    _write_csv(private / "assignments.csv", schedule, tuple(schedule[0]))
    (private / "answer_key.json").write_text(json.dumps(catalog, indent=2) + "\n")
    template = base / "responses.template.csv"
    _write_csv(template, [], RESPONSE_FIELDS)
    blind_key = []
    for name in ("sum", "off_by_one"):
        original = root / "audio" / "demos" / name / "execution.wav"
        if original.exists():
            label = "clip_" + hashlib.sha256(original.read_bytes()).hexdigest()[:10]
            destination = public / "blind_pair"
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination / f"{label}.wav")
            blind_key.append({"label": label, "original_demo": name, "sha256": hashlib.sha256(original.read_bytes()).hexdigest()})
    (private / "blind_pair_key.json").write_text(json.dumps(blind_key, indent=2) + "\n")
    manifest = {"generated_participant_sequences": participants, "scheduled_trials": len(schedule),
                "unique_stimuli": len(catalog), "participant_observations": 0,
                "condition_orders": ORDERS, "blind_pair_clips": len(blind_key),
                "condition_variant_counts": {f"{condition}:{variant}": sum(r["condition"] == condition and r["variant"] == variant for r in schedule) for condition in "ABC" for variant in range(3)},
                "note": "Scheduled rows are assignments, not participant responses. Researcher-only keys must be physically separated before distribution."}
    (private / "generation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def summarize_responses(path: Path) -> dict:
    """Summarize actual observed rows only; reject malformed or duplicate rows."""
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if set(RESPONSE_FIELDS) - set(reader.fieldnames or []):
            raise ValueError("Response CSV is missing required columns")
        rows = list(reader)
    seen = set()
    for row in rows:
        if not row["participant_id"] or not row["stimulus_id"]:
            raise ValueError("Missing participant/stimulus ID")
        if row["condition"] not in CONDITIONS or row["expected_abnormal"] not in {"0", "1"} or row["reported_abnormal"] not in {"0", "1"}:
            raise ValueError("Invalid condition or binary response")
        for field in ("trial", "elapsed_seconds", "confidence", "programming_years", "music_years", "training_seconds", *TLX):
            if row[field] == "" and field in TLX:
                row[field] = None
                continue
            try:
                value = float(row[field])
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid numeric field {field}") from exc
            if not math.isfinite(value) or value < 0 or (field in (*TLX, "confidence") and value > 100):
                raise ValueError(f"Out-of-range numeric field {field}")
            if field == "trial" and (not value.is_integer() or value < 1):
                raise ValueError("Trial must be a positive integer")
            row[field] = value
        row["trial"] = int(row["trial"])
        key = (row["participant_id"], row["trial"])
        if key in seen:
            raise ValueError("Repeated trial for participant")
        seen.add(key)
        if any(row[field] is None for field in TLX) and not all(row[field] is None for field in TLX):
            raise ValueError("Provide all six workload ratings or leave all blank")
        row["correct"] = row["expected_abnormal"] == row["reported_abnormal"]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["condition"]].append(row)
    conditions = {}
    for condition, own in grouped.items():
        normal = [r for r in own if r["expected_abnormal"] == "0"]
        abnormal = [r for r in own if r["expected_abnormal"] == "1"]
        workload = [statistics.mean(r[field] for field in TLX) for r in own if r[TLX[0]] is not None]
        conditions[condition] = {
            "observations": len(own), "accuracy": statistics.mean(r["correct"] for r in own),
            "false_positive_rate": statistics.mean(r["reported_abnormal"] == "1" for r in normal) if normal else None,
            "false_positive_denominator": len(normal),
            "false_negative_rate": statistics.mean(r["reported_abnormal"] == "0" for r in abnormal) if abnormal else None,
            "false_negative_denominator": len(abnormal),
            "median_seconds": statistics.median(r["elapsed_seconds"] for r in own),
            "mean_confidence": statistics.mean(r["confidence"] for r in own),
            "mean_raw_tlx": statistics.mean(workload) if workload else None,
            "workload_observations": len(workload),
        }
    people = defaultdict(list)
    for row in rows:
        people[row["participant_id"]].append(row)
    learning = []
    for person, own in people.items():
        ordered = sorted(own, key=lambda r: r["trial"])
        if len(ordered) >= 6:
            early, late = ordered[:3], ordered[-3:]
            learning.append({"participant_id": person,
                             "late_minus_early_accuracy": statistics.mean(r["correct"] for r in late) - statistics.mean(r["correct"] for r in early),
                             "late_minus_early_median_seconds": statistics.median(r["elapsed_seconds"] for r in late) - statistics.median(r["elapsed_seconds"] for r in early)})
    return {"observations": len(rows), "participants": len(people), "conditions": conditions,
            "learning_descriptors": learning,
            "interpretation": "Descriptive observed-data summary. Order, task difficulty, condition, and prior experience can confound differences. No causal or auditory-performance claim follows from generation or simulation."}
