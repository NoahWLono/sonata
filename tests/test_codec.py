from pathlib import Path

import mido
import pytest
from hypothesis import given, settings, strategies as st

from sonata.codec import encode_ast, decode_notes, compile_program, import_program
from sonata.language import parse, canonical
from sonata.runtime import execute

SOURCE = "let total = 0; for i in 1..6 { total = total + i; } return total;"


def test_notes_encode_the_program_without_metadata(tmp_path):
    ast = parse(SOURCE)
    path = tmp_path / "program.mid"
    notes = compile_program(ast, path)
    assert notes == encode_ast(ast)
    midi = mido.MidiFile(path)
    for track in midi.tracks:
        # Metadata is dispensable, including tempo and track names.
        track[:] = [m for m in track if not m.is_meta]
    midi.save(path)
    restored = import_program(path)
    assert canonical(restored) == canonical(ast)
    assert execute(restored)["return_value"] == 15


@settings(max_examples=50, derandomize=True)
@given(st.integers(min_value=-10000, max_value=10000), st.integers(min_value=0, max_value=30))
def test_generated_ast_note_roundtrips(initial, bound):
    ast = parse(f"let accumulator = {initial}; for i in 0..{bound} {{ accumulator = accumulator + i; }} return accumulator;")
    assert canonical(decode_notes(encode_ast(ast))) == canonical(ast)


def test_truncation_timing_and_pitch_corruption_are_rejected():
    notes = encode_ast(parse(SOURCE))
    for bad in [notes[:-1], [dict(n, start=n["start"] + .01) if i == 4 else n for i,n in enumerate(notes)], [dict(n, pitch=127) if i == 4 else n for i,n in enumerate(notes)]]:
        with pytest.raises(ValueError):
            decode_notes(bad)


def test_score_is_deterministic_and_formatting_independent(tmp_path):
    a, b = tmp_path / "a.mid", tmp_path / "b.mid"
    compile_program(parse(SOURCE), a)
    compile_program(parse("// comment\n" + SOURCE), b)
    assert a.read_bytes() == b.read_bytes()


def test_exhaustive_bounded_expression_note_alphabet():
    from sonata.codec import DIGITS, TOKEN_PITCHES
    assert len(set(DIGITS)) == 16
    assert len(set(TOKEN_PITCHES.values())) == len(TOKEN_PITCHES)
    sources = [f"return {a} {op} {b};" for a in (-1,0,1) for b in (-1,0,1)
               for op in ("+","-","*","/","%","==","!=","<","<=",">",">=")]
    sources += [f"return {op}{a};" for a in (-1,0,1) for op in ("+","-")]
    sources += [f"return {a} {op} {b};" for a in ("true","false") for b in ("true","false") for op in ("&&","||","==","!=")]
    sources += ["return !true;","return !false;"]
    assert len(sources) == 123
    scores = set()
    for source in sources:
        ast = parse(source)
        notes = encode_ast(ast)
        scores.add(tuple((n["start"],n["pitch"],n["channel"]) for n in notes))
        assert canonical(decode_notes(notes)) == canonical(ast)
    assert len(scores) == 123
