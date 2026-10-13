#!/usr/bin/env python3
"""Local user-supplied MIDI -> executable SONATA score -> MIDI bridge."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import mido
from sonata.language import parse
from sonata.midi_guard import checked_midi_bytes
from sonata.reference import evaluate
from sonata.runtime import execute, Limits

MAGIC = 1397706324
RADIX = 65536


def canonical_midi(midi):
    """Compare message content, exact deltas, track order, type, and PPQ."""
    return {
        "type": midi.type, "ticks_per_beat": midi.ticks_per_beat,
        "tracks": [[message.dict() for message in track] for track in midi.tracks],
    }


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def convert_midi(input_path, target, page_size=256):
    input_path, target = Path(input_path), Path(target)
    if type(page_size) is not int or not 1 <= page_size <= 256:
        raise ValueError("page_size must be in 1..256")
    midi = mido.MidiFile(file=io.BytesIO(checked_midi_bytes(input_path)))
    catalog, catalog_lookup, pages, tracks = [], {}, [], []
    for track_id, track in enumerate(midi.tracks):
        words = []
        for message in track:
            raw = tuple(message.bytes())
            if not (message.is_meta or 0x80 <= raw[0] < 0xF0):
                raise ValueError("only channel and meta messages are supported")
            if len(raw) > 256:
                raise ValueError("MIDI message exceeds SONATA array limit")
            if raw not in catalog_lookup:
                catalog_lookup[raw] = len(catalog)
                catalog.append(raw)
            words.append(message.time * RADIX + catalog_lookup[raw])
        first = len(pages)
        pages.extend(words[i:i+page_size] for i in range(0, len(words), page_size))
        tracks.append((track_id, first, len(pages), len(words)))
    if len(catalog) >= RADIX or sum(map(len, pages)) > 65536 or len(pages) > 4096:
        raise ValueError("arrangement exceeds local score bounds")
    lines = [
        "// Local performance converted from user-supplied MIDI.",
        "// Run with score_bridge.py perform; keep the .inputs.json beside this file.",
        "// Catalog arrays are raw MIDI messages; comments name their musical meaning.",
        "// Each fixture word = delta_ticks * 65536 + zero-based catalog index.",
        "// Editing a catalog print changes every use of that message in the score.",
        "fn perform_track(track_id, first_page, end_page, expected_events) {",
        "    print([track_id, end_page - first_page, expected_events]);",
        "    let emitted = 0;",
        "    for page in first_page..end_page {",
        "        let events = input(page);",
        "        assert(len(events) > 0);",
        "        emitted = emitted + len(events);",
        "        print(events);",
        "    }",
        "    assert(emitted == expected_events);",
        "    return emitted;",
        "}",
        "// Protocol magic, version, PPQ, MIDI type, tracks, catalog entries.",
        f"print([{MAGIC}, 1, {midi.ticks_per_beat}, {midi.type}, {len(tracks)}, {len(catalog)}]);",
    ]
    for index, raw in enumerate(catalog):
        message = decode_message(raw)
        description = str(message).replace("\n", " ").replace("\r", " ")
        # JSON escaping keeps externally supplied text on a single comment line.
        lines.append(f"print({list(raw)}); // {index}: {json.dumps(description, ensure_ascii=True)}")
    lines.extend(["", "// Emit tracks in their original order, preserving simultaneous-event order.",
                  "let total_events = 0;"])
    for track_id, first, end, count in tracks:
        lines.append(f"total_events = total_events + perform_track({track_id}, {first}, {end}, {count});")
    lines.extend([f"assert(total_events == {sum(map(len, pages))});", "return total_events;", ""])
    source = "\n".join(lines)
    parse(source)  # Validate against the unchanged v1 language before saving.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    target.with_suffix(".inputs.json").write_text(json.dumps(pages, separators=(",", ":")) + "\n")
    return {"catalog_entries": len(catalog), "messages": sum(map(len, pages)),
            "pages": len(pages), "tracks": len(tracks)}


def decode_message(raw):
    if not raw or len(raw) > 256 or any(type(x) is not int or not 0 <= x <= 255 for x in raw):
        raise ValueError("invalid message catalog bytes")
    if raw[0] == 0xFF:
        return mido.MetaMessage.from_bytes(list(raw))
    if not 0x80 <= raw[0] < 0xF0:
        raise ValueError("unsupported message catalog status")
    return mido.Message.from_bytes(list(raw))


def decode_output(output, returned):
    cursor = 0

    def take():
        nonlocal cursor
        if cursor >= len(output):
            raise ValueError("truncated performance output")
        row = output[cursor]
        cursor += 1
        if type(row) is not list or not row or any(type(x) is not int for x in row):
            raise ValueError("performance records must be nonempty integer arrays")
        return row

    header = take()
    if len(header) != 6 or header[:2] != [MAGIC, 1]:
        raise ValueError("invalid performance header")
    _, _, ppq, kind, track_count, catalog_count = header
    if (not 0 < ppq < 32768 or kind not in (0, 1) or not 1 <= track_count <= 64
            or (kind == 0 and track_count != 1) or not 0 < catalog_count < RADIX):
        raise ValueError("invalid MIDI dimensions")
    catalog = [decode_message(take()) for _ in range(catalog_count)]
    midi = mido.MidiFile(type=kind, ticks_per_beat=ppq)
    total = 0
    for track_id in range(track_count):
        track_header = take()
        if len(track_header) != 3 or track_header[0] != track_id:
            raise ValueError("invalid track header")
        _, page_count, expected = track_header
        if not 1 <= page_count <= 4096 or not 1 <= expected <= 65536:
            raise ValueError("invalid track counts")
        track, absolute = mido.MidiTrack(), 0
        for _ in range(page_count):
            row = take()
            if len(row) > 256:
                raise ValueError("oversized performance page")
            for word in row:
                if word < 0:
                    raise ValueError("negative performance word")
                delta, index = divmod(word, RADIX)
                if index >= len(catalog):
                    raise ValueError("invalid message catalog index")
                absolute += delta
                if absolute > 0x0FFFFFFF:
                    raise ValueError("MIDI track exceeds timing bound")
                track.append(catalog[index].copy(time=delta))
        if len(track) != expected:
            raise ValueError("track event count mismatch")
        if track[-1].type != "end_of_track" or any(m.type == "end_of_track" for m in track[:-1]):
            raise ValueError("track must end with exactly one end_of_track")
        midi.tracks.append(track)
        total += len(track)
        if total > 65536:
            raise ValueError("performance exceeds message bound")
    if cursor != len(output) or type(returned) is not int or returned != total:
        raise ValueError("unexpected extra records or return value")
    return midi


def run_score(source_path, output_path=None):
    source_path = Path(source_path)
    source = source_path.read_text(encoding="utf-8")
    fixture_path = source_path.with_suffix(".inputs.json")
    if fixture_path.stat().st_size > 2_000_000:
        raise ValueError("input fixture exceeds 2 MB")
    inputs = json.loads(fixture_path.read_text())
    result = execute(parse(source), limits=Limits(max_steps=100_000), inputs=inputs)
    if result["error"]:
        raise ValueError(f"SONATA execution failed: {result['error']}")
    reference = evaluate(source, fuel=100_000, max_array=256, inputs=inputs)
    reference_equal = all(result[key] == reference[key] for key in ("output", "return_value", "error"))
    if not reference_equal:
        raise ValueError("independent reference execution disagrees")
    midi = decode_output(result["output"], result["return_value"])
    report = {
        "reference_equal": reference_equal,
        "source_sha256": sha256(source_path), "fixture_sha256": sha256(fixture_path),
        "messages": sum(map(len, midi.tracks)),
        "note_on_count": sum(m.type == "note_on" and m.velocity > 0 for t in midi.tracks for m in t),
        "tracks": len(midi.tracks), "duration_seconds": midi.length,
        "trace_events": len(result["trace"]),
        "independence_limit": "Reference evaluator shares the parser; both MIDI paths use mido.",
    }
    if output_path is not None:
        output_path = Path(output_path)
        midi.save(output_path)
        restored = mido.MidiFile(file=io.BytesIO(checked_midi_bytes(output_path)))
        if canonical_midi(restored) != canonical_midi(midi):
            raise ValueError("saved MIDI differs from executed performance")
        report["midi_sha256"] = sha256(output_path)
    return midi, result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert", help="convert user-supplied MIDI into a SONATA score and fixtures")
    convert.add_argument("input", type=Path)
    convert.add_argument("source", type=Path)
    perform = commands.add_parser("perform", help="execute SONATA, verify with reference, and save MIDI")
    perform.add_argument("source", type=Path)
    perform.add_argument("--midi", type=Path)
    args = parser.parse_args()
    if args.command == "convert":
        stats = convert_midi(args.input, args.source)
        midi, _, report = run_score(args.source, args.source.with_suffix(".mid"))
        original = mido.MidiFile(file=io.BytesIO(checked_midi_bytes(args.input)))
        if canonical_midi(original) != canonical_midi(midi):
            raise ValueError("converted performance differs from original MIDI")
        report.update(stats)
        report.update({"original_path": str(args.input.resolve()),
                       "original_sha256": sha256(args.input), "original_event_equality": True})
        report_path = args.source.with_suffix(".verification.json")
    else:
        _, _, report = run_score(args.source, args.midi or args.source.with_suffix(".mid"))
        report_path = args.source.with_suffix(".performance-report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
