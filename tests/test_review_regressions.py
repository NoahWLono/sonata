from pathlib import Path
import subprocess
import sys

import pytest

from sonata.language import parse, canonical, format_source
from sonata.codec import encode_ast, decode_notes
from sonata.runtime import execute
from sonata.midi import read_midi


def test_nested_expression_score_reconstructs():
    expression = "1"
    for _ in range(17):
        expression = "1+1*(" + expression + ")"
    ast = parse("return " + expression + ";")
    restored = decode_notes(encode_ast(ast))
    assert canonical(restored) == canonical(ast)
    assert execute(restored)["return_value"] == 18


def test_score_avoids_indentation_expansion_limit():
    source = "if(true){" * 25 + "1;" * 2500 + "}" * 25
    ast = parse(source)
    assert canonical(decode_notes(encode_ast(ast))) == canonical(ast)


@pytest.mark.parametrize("expression", ["1-(2-3)", "(1+2)*3", "1+(2+3)", "-(1+2)", "1*(2/3)", "-(-1)", "[1,2][1]", "!(true&&false)"])
def test_printer_preserves_expression_tree(expression):
    ast = parse("return " + expression + ";")
    assert canonical(parse(format_source(ast))) == canonical(ast)


def test_array_index_effects_resolve_current_binding():
    result = execute(parse("let a=[1,2]; fn idx(){a=[3,4];return 0;} a[idx()]=9;return a;"))
    assert result["return_value"] == [9,4]
    assert result["globals"]["a"] == [9,4]
    assignment = [e for e in result["trace"] if e["kind"] == "assign"][-1]
    assert assignment["variables"]["a"] == [9,4]


def test_overlong_midi_variable_length_quantity_is_rejected(tmp_path):
    track = b"\xff" * 32 + b"\x00\xff\x2f\x00"
    path = tmp_path / "malformed.mid"
    path.write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk" + len(track).to_bytes(4,"big") + track)
    with pytest.raises(ValueError, match="variable|VLQ"):
        read_midi(path)


def test_empty_midi_cli_error_is_structured(tmp_path):
    path = tmp_path / "empty.mid"
    path.write_bytes(b"")
    result = subprocess.run([sys.executable,"-m","sonata","decode",str(path)],capture_output=True,text=True)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("count", [128,256,4096])
def test_dense_bounded_array_midi_preserves_every_note(tmp_path,count):
    from sonata.runtime import Limits
    from sonata.music import sonify
    from sonata.midi import write_midi
    source = "return [" + ",".join(["1"]*count) + "];"
    notes = sonify(execute(parse(source),Limits(max_array=4096))["trace"],palette="ambient")
    path=tmp_path/"dense.mid"
    write_midi(notes,path,palette="ambient")
    restored=read_midi(path)
    assert len(restored)==len(notes)
    assert all(n["duration"]>0 for n in restored)
