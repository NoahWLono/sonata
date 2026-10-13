#!/usr/bin/env python3
"""Prepare study packets or summarize an observed-response CSV."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from research.study import generate_kit, summarize_responses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--root", type=Path, default=ROOT)
    generate.add_argument("--participants", type=int, default=6)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("csv", type=Path)
    analyze.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = generate_kit(args.root, args.participants) if args.command == "generate" else summarize_responses(args.csv)
    text = json.dumps(result, indent=2) + "\n"
    if args.command == "analyze" and args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
