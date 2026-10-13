"""Validated operations shared by the local debugger and its HTTP transport."""
import json

from .codec import encode_ast, TOKEN_PITCHES
from .language import parse, format_source, _tokens
from .music import sonify
from .runtime import execute, Limits

WEB_LIMITS = Limits(max_steps=3000, max_depth=16, max_array=128, timeout_seconds=1)


def read_inputs(args):
    if "inputs_json" in args:
        raw = args["inputs_json"]
        if not isinstance(raw, str) or len(raw) > 20_000:
            raise ValueError("Input fixtures must be JSON text of at most 20000 characters")
        values = json.loads(raw)
    else:
        values = args.get("inputs", [])
    if not isinstance(values, list):
        raise ValueError("Input fixtures must be a JSON array")
    return values


def code_score(ast):
    """Attach editable-token provenance without changing the SC1 note grammar."""
    tokens = [token.text for token in _tokens(format_source(ast, compact=True))
              if token.text != "<eof>"]
    notes = encode_ast(ast)
    offset = 3  # Three simultaneous header notes.
    for index, token in enumerate(tokens):
        count = 1 if token in TOKEN_PITCHES else 2 + 2 * len(token.encode("ascii"))
        for note in notes[offset:offset + count]:
            note["token_index"] = index
        offset += count
    return tokens, notes


def run_payload(args):
    if not isinstance(args, dict):
        raise ValueError("Expected a program object")
    source = args.get("source")
    if not isinstance(source, str) or len(source) > 20_000:
        raise ValueError("Source must contain at most 20000 characters")
    ast = parse(source)
    result = execute(ast, WEB_LIMITS, inputs=read_inputs(args))
    notes = sonify(result["trace"], palette=args.get("palette", "classical"),
                   profile=args.get("profile"))
    tokens, score = code_score(ast)
    return {"source": source, "code_source": format_source(ast, compact=True),
            "result": result, "notes": notes, "code_notes": score, "code_tokens": tokens}


def edit_score(args):
    tokens = args.get("tokens")
    if not isinstance(tokens, list) or not 1 <= len(tokens) <= 10_000:
        raise ValueError("A score must contain 1..10000 token cells")
    for token in tokens:
        if not isinstance(token, str) or not 1 <= len(token) <= 128:
            raise ValueError("Each score cell must be one token of at most 128 characters")
        parsed = [t.text for t in _tokens(token) if t.text != "<eof>"]
        if parsed != [token]:
            raise ValueError("Each score cell must contain exactly one language token")
    source = " ".join(tokens)
    # Parse before changing the accepted source. A malformed edit returns an error.
    ast = parse(source)
    return run_payload({**args, "source": format_source(ast, compact=True)})


def compare_payload(args):
    from .comparison import compare_traces
    programs = []
    for side in ("left", "right"):
        program = args.get(side)
        if not isinstance(program, dict):
            raise ValueError(f"{side} must be a program object")
        programs.append(run_payload({**program, "palette": args.get("palette", "classical"),
                                     "profile": args.get("profile")}))
    left, right = programs
    report = compare_traces(left["result"]["trace"], right["result"]["trace"])
    report["first_event_divergence"] = report["first_divergence"]
    keys = ("start", "duration", "pitch", "velocity", "channel")
    a = [tuple(n[key] for key in keys) for n in left["notes"]]
    b = [tuple(n[key] for key in keys) for n in right["notes"]]
    report["first_note_divergence"] = next((i for i in range(max(len(a), len(b)))
                                           if i >= len(a) or i >= len(b) or a[i] != b[i]), None)
    return {"left": left, "right": right, "comparison": report}
