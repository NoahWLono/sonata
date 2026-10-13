from pathlib import Path

import pytest
from sonata.language import parse, canonical
from sonata.runtime import execute, Limits
from sonata.reference import evaluate_reference
from sonata.codec import encode_ast, decode_notes

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize("name,expected", [("sum",15), ("off_by_one",10), ("factorial",120), ("fibonacci",5), ("bubble_sort",[1,2,3,4,5]), ("binary_search",4), ("binary_search_miss",-1)])
def test_demonstrations_and_reference(name, expected):
    source = (EXAMPLES / f"{name}.son").read_text()
    ast = parse(source)
    restored = decode_notes(encode_ast(ast))
    assert canonical(ast) == canonical(restored)
    actual = execute(ast)
    assert actual["error"] is None
    assert actual["return_value"] == expected
    reference = evaluate_reference(source)
    assert reference["return_value"] == expected
    assert actual["output"] == reference["output"]


def test_recursion_stops_at_limit_with_growing_depth():
    actual = execute(parse((EXAMPLES / "infinite_recursion.son").read_text()), Limits(max_depth=12))
    assert actual["error"] is not None
    assert actual["error"]["kind"] == "DepthLimit"
    assert max(e["depth"] for e in actual["trace"]) == 12
    assert actual["trace"][-1]["kind"] == "error"
