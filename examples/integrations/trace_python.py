"""Observe a trusted Python function and export its actual execution as music."""
import argparse
import json
from pathlib import Path
from sonata.python_trace import trace_callable, validate_trace_bundle
from sonata.music import sonify
from sonata.audio import render_wav
from sonata.midi import write_midi


def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', default='artifacts/python-fibonacci')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    bundle = validate_trace_bundle(trace_callable(fibonacci, 5))
    assert bundle['return_value'] == 5 and bundle['error'] is None
    notes = sonify(bundle['trace'], profile={'mapping': 'semantic'})
    (output / 'trace.json').write_text(json.dumps(bundle, indent=2) + '\n', encoding='utf-8')
    (output / 'notes.json').write_text(json.dumps(notes, indent=2) + '\n', encoding='utf-8')
    write_midi(notes, output / 'execution.mid')
    render_wav(notes, output / 'execution.wav')
    print(f"fibonacci(5) = 5; exported {len(bundle['trace'])} events to {output}")


if __name__ == '__main__':
    main()
