import pytest

from sonata.language import SonataSyntaxError, canonical, format_source, parse
from sonata.runtime import Limits, execute


def test_sum_one_through_five_and_trace():
    source = "let total = 0; for i in 1..6 { total = total + i; } print(total); return total;"
    ast = parse(source)
    result = execute(ast)
    assert result["error"] is None
    assert result["output"] == [15]
    assert result["return_value"] == 15
    assert result["globals"] == {"total": 15}
    assert [event["id"] for event in result["trace"]] == list(range(len(result["trace"])))
    checks = [event["data"]["taken"] for event in result["trace"] if event["kind"] == "loop"]
    assert checks == [True, True, True, True, True, False]
    assert canonical(parse(format_source(ast))) == canonical(ast)


@pytest.mark.parametrize(("expression", "expected"), [
    ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("9 - 2 - 1", 6),
    ("-7 / 3", -2), ("7 / -3", -2), ("-7 % 3", -1), ("7 % -3", 1),
    ("true && !false", True), ("false || true", True), ("3 <= 3", True),
    ("4 >= 9", False), ("1 != 2", True), ("[1, 2] == [1, 2]", True),
    ("[1] != [2]", True), ("len([1, 2, 3])", 3), ("[][0]", "IndexError"),
    ("-9223372036854775808", -(2**63)), ("9223372036854775807 + 1", "Overflow"),
    ("-9223372036854775808 / -1", "Overflow"), ("1 / 0", "DivisionByZero"),
    ("1 % 0", "DivisionByZero"), ("1 + true", "TypeError"), ("1 == true", "TypeError"),
    ("!1", "TypeError"), ("[true]", "TypeError"), ("len(1)", "TypeError"),
    ("[1][-1]", "IndexError"), ("[1][true]", "TypeError"),
    ("false && (1 / 0 == 0)", False), ("true || (1 / 0 == 0)", True),
])
def test_expression_semantics(expression, expected):
    result = execute(parse(f"return {expression};"))
    if isinstance(expected, str):
        assert result["error"]["kind"] == expected
        assert result["trace"][-1]["kind"] == "error"
    else:
        assert result["error"] is None
        assert result["return_value"] == expected
        assert type(result["return_value"]) is type(expected)


def test_while_conditions_and_branch_choices():
    result = execute(parse("let x = 0; while (x < 3) { x = x + 1; } if (x == 3) { print(10); } else { print(20); }"))
    assert result["error"] is None
    assert result["output"] == [10]
    assert [e["data"]["taken"] for e in result["trace"] if e["kind"] == "loop"] == [True, True, True, False]
    assert [e["data"]["taken"] for e in result["trace"] if e["kind"] == "branch"] == [True]


def test_recursive_function_and_return_unwind():
    source = "fn fib(n) { if (n <= 1) { return n; } return fib(n-1) + fib(n-2); } return fib(8);"
    result = execute(parse(source))
    assert result["error"] is None
    assert result["return_value"] == 21
    calls = [e for e in result["trace"] if e["kind"] == "call"]
    assert max(e["depth"] for e in calls) == 8
    assert calls[0]["function"] == "fib"
    assert calls[0]["variables"] == {"n": 8}
    assert canonical(parse(format_source(parse(source)))) == canonical(parse(source))


def test_mutual_recursion_and_forward_call():
    result = execute(parse("return even(10); fn even(n) { if (n == 0) { return true; } return odd(n-1); } fn odd(n) { if (n == 0) { return false; } return even(n-1); }"))
    assert result["error"] is None
    assert result["return_value"] is True


def test_function_lexical_scope_and_global_assignment():
    result = execute(parse("let x = 1; fn f() { x = x + 1; return x; } fn g(x) { let y = 42; return f(); } return g(99);"))
    assert result["error"] is None
    assert result["return_value"] == 2
    assert result["globals"] == {"x": 2}
    fcall = next(e for e in result["trace"] if e["kind"] == "call" and e["function"] == "f")
    assert fcall["variables"] == {"x": 1}
    assert fcall["stack"] == ["<main>", "g", "f"]


def test_arrays_copy_on_assignment_argument_return_and_trace():
    source = "let a = [1, 2]; let b = a; b[0] = 9; fn f(c) { c[1] = 8; return c; } let d = f(a); print(a); print(b); return d;"
    result = execute(parse(source))
    assert result["error"] is None
    assert result["output"] == [[1, 2], [9, 2]]
    assert result["return_value"] == [1, 8]
    assert result["globals"] == {"a": [1, 2], "b": [9, 2], "d": [1, 8]}
    declared_b = next(e for e in result["trace"] if e["kind"] == "declare" and e["data"]["name"] == "b")
    assert declared_b["variables"]["b"] == [1, 2]


@pytest.mark.parametrize(("source", "kind"), [
    ("return nope;", "NameError"), ("x = 1;", "NameError"),
    ("let x = 1; let x = 2;", "NameError"), ("let x = 1; x = true;", "TypeError"),
    ("let a = [1]; a[0] = false;", "TypeError"), ("let a = [1]; a[1] = 2;", "IndexError"),
    ("if (1) { return 1; }", "TypeError"), ("while (0) {}", "TypeError"),
    ("for i in true..5 {}", "TypeError"), ("return len();", "ArityError"),
    ("return print(1, 2);", "ArityError"), ("fn f(x) { return x; } return f();", "ArityError"),
    ("fn f() { return secret; } fn g() { let secret = 4; return f(); } return g();", "NameError"),
    ("return unknown();", "NameError"), ("fn len() { return 1; }", "NameError"),
    ("fn f() {} fn f() {}", "NameError"), ("fn f(x, x) {}", "NameError"),
])
def test_semantic_errors_are_structured(source, kind):
    result = execute(parse(source))
    assert result["error"]["kind"] == kind
    assert result["error"]["line"] >= 1
    assert result["trace"][-1]["kind"] == "error"


def test_function_fallthrough_and_block_scopes():
    result = execute(parse("let x = 5; if (true) { let x = 7; print(x); } fn f() { let x = 9; } print(f()); return x;"))
    assert result["error"] is None
    assert result["output"] == [7, 0]
    assert result["return_value"] == 5


@pytest.mark.parametrize(("source", "limits", "kind"), [
    ("while (true) {}", Limits(max_steps=30), "StepLimit"),
    ("fn f() { return f(); } return f();", Limits(max_depth=4), "DepthLimit"),
    ("return [1, 2, 3];", Limits(max_array=2), "ArrayLimit"),
    ("return 1;", Limits(timeout_seconds=0), "Timeout"),
])
def test_execution_limits(source, limits, kind):
    result = execute(parse(source), limits)
    assert result["error"]["kind"] == kind
    assert result["trace"][-1]["kind"] == "error"
    assert result["instructions"] <= limits.max_steps


@pytest.mark.parametrize("source", ["let x = ;", "let true = 1;", "return 1", "return @;", "fn f() {", "if (true) { fn f() {} }", "return " + "(" * 200 + "1" + ")" * 200 + ";", "return " + " + ".join(["1"] * 300) + ";"])
def test_syntax_errors_are_bounded_and_located(source):
    with pytest.raises(SonataSyntaxError) as caught:
        parse(source)
    assert caught.value.line >= 1
    assert caught.value.col >= 1


def test_formatter_roundtrip_all_constructs():
    source = "// heading\nlet a = [1,2]; fn f(n) { while (n > 0) { n = n - 1; } if (!false) { return len(a); } else { return 0; } }; for i in 0..2 { a[i] = f(i); } return a;"
    ast = parse(source)
    assert canonical(parse(format_source(ast))) == canonical(ast)


def test_repeat_execution_is_deterministic_and_does_not_mutate_ast():
    ast = parse("let a = [3, 1]; a[1] = 2; return a;")
    original = canonical(ast)
    assert execute(ast) == execute(ast)
    assert canonical(ast) == original


@pytest.mark.parametrize("ast", [{}, {"kind": "program", "body": 1}, {"kind": "program", "body": [{"kind": "return"}]}, {"kind": "program", "body": [{"kind": "return", "value": {"kind": "unary", "op": "evil", "value": {"kind": "int", "value": 1}}}]}])
def test_malformed_ast_returns_structured_failure(ast):
    result = execute(ast)
    assert result["error"]["kind"] == "InvalidAST"
    assert result["trace"][-1]["kind"] == "error"


def test_cyclic_ast_returns_structured_failure():
    ast = {"kind": "program", "body": []}
    ast["body"].append(ast)
    assert execute(ast)["error"]["kind"] == "InvalidAST"


@pytest.mark.parametrize("kwargs", [{"max_steps": 0}, {"max_steps": True}, {"max_depth": -1}, {"max_array": -1}, {"timeout_seconds": -1}, {"timeout_seconds": float("nan")}, {"max_steps": 2**60}])
def test_invalid_limits_rejected(kwargs):
    with pytest.raises(ValueError):
        Limits(**kwargs)


def test_failure_retains_innermost_variables_and_stack():
    result = execute(parse("fn fail(n) { if (true) { let secret = 9; return n / 0; } } return fail(3);"))
    assert result["error"]["kind"] == "DivisionByZero"
    event = result["trace"][-1]
    assert event["variables"] == {"n": 3, "secret": 9}
    assert event["stack"] == ["<main>", "fail"]


def test_short_circuit_trace_records_rhs_decision():
    result = execute(parse("return false && (1 / 0 == 0);"))
    decision = next(e for e in result["trace"] if e["kind"] == "branch")
    assert decision["data"]["operator"] == "&&"
    assert decision["data"]["taken"] is False


def test_trace_memory_budget_is_bounded():
    result = execute(parse("let a = [1, 2, 3]; while (true) { print(a); }"), Limits(max_trace_values=60))
    assert result["error"]["kind"] == "TraceLimit"
    assert result["instructions"] < 100


def test_combined_recursion_and_expression_depth_are_bounded():
    source = "fn f(n) { return " + "(" * 25 + "f(n+1)" + "+1)" * 25 + "; } return f(0);"
    result = execute(parse(source), Limits(max_depth=100))
    assert result["error"]["kind"] == "DepthLimit"


def test_source_identifier_length_is_bounded():
    with pytest.raises(SonataSyntaxError):
        parse("let " + "x" * 300 + " = 0;")


@pytest.mark.parametrize("expression", ["!" * 50 + "true", "(-1)[0]", "-(1 + 2)", "-(-1)[0]"])
def test_formatter_preserves_deep_unary_and_index_precedence(expression):
    ast = parse(f"return {expression};")
    assert canonical(parse(format_source(ast))) == canonical(ast)
