"""Command line entry points; errors remain structured and bounded."""
import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .cli_io import read_json, save_json


def _limits_options(parser):
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--max-depth", type=int, default=32)
    parser.add_argument("--max-array", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=3.0)


def _music_options(parser):
    parser.add_argument("--palette", choices=("classical", "electronic", "ambient"), default="classical")
    parser.add_argument("--bpm", type=float, default=120)
    profile = parser.add_mutually_exclusive_group()
    profile.add_argument("--profile", type=Path, help="Versioned JSON listening profile")
    profile.add_argument("--semantic", action="store_true", help="Use stable semantic motifs")


def arguments(argv):
    parser = argparse.ArgumentParser(prog="sonata", description="Write an algorithm. Hear it execute.")
    parser.add_argument("--version", action="version", version=f"SONATA {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "listen", "compile", "decode", "verify", "debug", "bundle"):
        p = commands.add_parser(name)
        if name == "debug":
            p.add_argument("source", type=Path, nargs="?", help="Defaults to the packaged sum example")
        else:
            p.add_argument("source", type=Path)
        if name in ("run", "listen", "verify"):
            _limits_options(p)
            p.add_argument("--inputs", type=Path, help="Ordered JSON array of input fixtures")
        if name in ("listen", "compile"):
            p.add_argument("--midi", type=Path)
        if name == "listen":
            p.add_argument("--wav", type=Path, required=True)
            p.add_argument("--trace", type=Path)
            p.add_argument("--stems", type=Path, help="Export each voice as WAV and MIDI")
            _music_options(p)
        if name == "run":
            p.add_argument("--trace", type=Path)
        if name in ("decode", "bundle"):
            p.add_argument("--output", type=Path)
        if name == "verify":
            p.add_argument("--report", type=Path)
        if name == "debug":
            p.add_argument("--port", type=int, default=8765)
            p.add_argument("--open", action="store_true")
    p = commands.add_parser("examples", help="Copy installed example resources")
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("compare", help="Compare the exact behavior of two recorded executions")
    p.add_argument("left", type=Path)
    p.add_argument("right", type=Path)
    p.add_argument("--left-inputs", type=Path)
    p.add_argument("--right-inputs", type=Path)
    p.add_argument("--report", type=Path)
    p.add_argument("--wav-dir", type=Path)
    _limits_options(p)
    _music_options(p)
    midi = commands.add_parser("midi", help="Optional live MIDI ports and recorded input replay")
    sub = midi.add_subparsers(dest="midi_command", required=True)
    sub.add_parser("ports")
    p = sub.add_parser("inputs", help="Convert recorded note-on messages to SONATA input fixtures")
    p.add_argument("file", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-notes", type=int, default=256)
    for name in ("play", "record", "replay"):
        p = sub.add_parser(name)
        p.add_argument("file", type=Path)
        p.add_argument("--port", required=True, help="Exact physical or virtual MIDI port name")
        if name == "record":
            p.add_argument("--seconds", type=float, default=10)
        else:
            p.add_argument("--speed", type=float, default=1)
    return parser.parse_args(argv)


def _profile(args):
    if args.profile:
        return read_json(args.profile)
    return {"version": 1, "mapping": "semantic"} if args.semantic else None


def _compare(args, limits):
    from .loader import load_source
    from .language import parse
    from .runtime import execute
    from .comparison import compare_traces
    from .music import sonify
    from .audio import render_wav
    runs = []
    for side in ("left", "right"):
        inputs = getattr(args, side + "_inputs")
        runs.append(execute(parse(load_source(getattr(args, side))), limits,
                            inputs=read_json(inputs) if inputs else None))
    report = compare_traces(runs[0]["trace"], runs[1]["trace"])
    report["results"] = [{key: run[key] for key in ("return_value", "output", "error")} for run in runs]
    if args.wav_dir:
        args.wav_dir.mkdir(parents=True, exist_ok=True)
        for name, run in zip(("left", "right"), runs):
            render_wav(sonify(run["trace"], palette=args.palette, profile=_profile(args)),
                       args.wav_dir / f"{name}.wav", bpm=args.bpm, palette=args.palette)
    if args.report:
        save_json(args.report, report)
    return report


def main(argv=None):
    args = arguments(argv)
    try:
        from .language import parse, format_source
        from .runtime import execute, Limits
        if args.command == "examples":
            from .cli_io import install_examples
            print(json.dumps(install_examples(args.output), indent=2))
            return 0
        if args.command == "midi":
            from .cli_io import midi_command
            print(json.dumps(midi_command(args), indent=2))
            return 0
        if args.command == "debug":
            from .server import serve
            serve(args.source, args.port, args.open)
            return 0
        if args.command == "decode":
            from .codec import import_program
            source = format_source(import_program(args.source))
            if args.output:
                args.output.write_text(source, encoding="utf-8")
            else:
                print(source, end="")
            return 0
        if args.command == "compare":
            limits = Limits(max_steps=args.max_steps, max_depth=args.max_depth,
                            max_array=args.max_array, timeout_seconds=args.timeout)
            print(json.dumps(_compare(args, limits), indent=2))
            return 0
        from .loader import load_source
        source = load_source(args.source)
        ast = parse(source)
        if args.command == "bundle":
            if args.output:
                args.output.write_text(source, encoding="utf-8")
            else:
                print(source, end="" if source.endswith("\n") else "\n")
            return 0
        if args.command == "compile":
            from .codec import compile_program
            path = args.midi or args.source.with_suffix(".code.mid")
            notes = compile_program(ast, path)
            print(json.dumps({"midi": str(path), "notes": len(notes), "mode": "executable-source"}))
            return 0
        limits = Limits(max_steps=args.max_steps, max_depth=args.max_depth,
                        max_array=args.max_array, timeout_seconds=args.timeout)
        inputs = read_json(args.inputs) if args.inputs else None
        if args.command == "verify":
            from .validation import verify
            result = verify(source, limits=limits, inputs=inputs)
            if args.report:
                save_json(args.report, result)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
        result = execute(ast, limits, inputs=inputs)
        if args.trace:
            save_json(args.trace, result)
        if args.command == "listen":
            from .music import sonify
            from .audio import render_wav
            from .midi import write_midi
            notes = sonify(result["trace"], palette=args.palette, profile=_profile(args))
            metrics = render_wav(notes, args.wav, bpm=args.bpm, palette=args.palette)
            if args.midi:
                write_midi(notes, args.midi, bpm=args.bpm, palette=args.palette)
            stems = None
            if args.stems:
                from .musiclib import export_stems
                stems = export_stems(notes, args.stems, bpm=args.bpm, palette=args.palette)
            result = {"return_value": result["return_value"], "error": result["error"],
                      "wav": str(args.wav), "notes": len(notes), "audio": metrics, "stems": stems}
        else:
            result = {k: v for k, v in result.items() if k != "trace"}
        print(json.dumps(result, indent=2))
        return 1 if result.get("error") else 0
    except (ValueError, TypeError, OSError, OverflowError, RecursionError, EOFError, RuntimeError, ImportError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
