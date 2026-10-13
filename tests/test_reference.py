"""Hand-derived semantic checks for the independent evaluator."""

import random

import pytest

from sonata.reference import evaluate


def test_reference_sum_counts_end_exclusively():
    result = evaluate(
        "let total = 0; for i in 1..6 { total = total + i; } "
        "print(total); return total;"
    )
    assert result == {
        "return_value": 15,
        "output": [15],
        "globals": {"total": 15},
        "error": None,
    }


def test_reference_off_by_one_changes_result():
    result = evaluate("let s=0; for i in 1..5 { s=s+i; } return s;")
    assert result["error"] is None
    assert result["return_value"] == 10


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("return 7 / 3;", 2),
        ("return -7 / 3;", -2),
        ("return 7 / -3;", -2),
        ("return -7 / -3;", 2),
        ("return -7 % 3;", -1),
        ("return 7 % -3;", 1),
        ("return 9223372036854775807 / 3;", 3074457345618258602),
        ("return -9223372036854775808;", -9223372036854775808),
        ("return 2 + 3 * 4 - 5;", 9),
        ("return !(3 < 2) && 3 >= 3 && 2 <= 3 && 4 > 3;", True),
        ("return false && (1/0 == 0);", False),
        ("return true || (1/0 == 0);", True),
        ("return [1,2] == [1,2];", True),
        ("return [1] != [2];", True),
        ("return len([]);", 0),
    ],
)
def test_reference_expressions(source, expected):
    result = evaluate(source)
    assert result["error"] is None
    assert result["return_value"] == expected
    assert type(result["return_value"]) is type(expected)


def test_reference_lexical_blocks_and_while():
    result = evaluate(
        "let n=0; let total=0; while (n < 4) { "
        "let square=n*n; total=total+square; n=n+1; } "
        "if (total == 14) { let n=99; print(n); } else { print(0); } return n;"
    )
    assert result == {
        "return_value": 4,
        "output": [99],
        "globals": {"n": 4, "total": 14},
        "error": None,
    }


def test_reference_ascending_loop_evaluates_bounds_once():
    result = evaluate(
        "let n=4; let total=0; for i in 0..n { total=total+i; n=0; } "
        "for unused in 4..1 { total=99; } return total;"
    )
    assert result["error"] is None
    assert result["return_value"] == 6
    assert result["globals"] == {"n": 0, "total": 6}


def test_reference_function_recursion_and_early_return():
    result = evaluate(
        "return fib(8); fn fib(n) { if (n < 2) { return n; } "
        "return fib(n-1)+fib(n-2); }"
    )
    assert result["error"] is None
    assert result["return_value"] == 21


def test_reference_function_reads_globals_instead_of_caller_locals():
    result = evaluate(
        "let x=7; fn read() { return x; } "
        "fn caller(x) { return read(); } return caller(99);"
    )
    assert result["error"] is None
    assert result["return_value"] == 7


def test_reference_mutual_recursion_and_fallthrough():
    result = evaluate(
        "fn even(n) { if (n==0) { return true; } return odd(n-1); } "
        "fn odd(n) { if (n==0) { return false; } return even(n-1); } "
        "fn nothing() { } print(nothing()); return even(8);"
    )
    assert result["error"] is None
    assert result["return_value"] is True
    assert result["output"] == [0]


def test_reference_arrays_are_values_and_print_snapshots_its_argument():
    result = evaluate(
        "fn edit(a) { a[0]=9; return a; } "
        "let a=[1,2]; let b=a; b[0]=3; "
        "let c=edit(a); print(a); a[1]=4; "
        "print(b); print(c); return a;"
    )
    assert result == {
        "return_value": [1, 4],
        "output": [[1, 2], [3, 2], [9, 2]],
        "globals": {"a": [1, 4], "b": [3, 2], "c": [9, 2]},
        "error": None,
    }


def test_reference_print_returns_argument_and_evaluates_left_to_right():
    result = evaluate("return print(3)+print(4);")
    assert result["error"] is None
    assert result["return_value"] == 7
    assert result["output"] == [3, 4]


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("return unknown;", "NameError"),
        ("missing=3;", "NameError"),
        ("let a=1; let a=2;", "NameError"),
        ("let a=1; a=true;", "TypeError"),
        ("return true+1;", "TypeError"),
        ("return true==1;", "TypeError"),
        ("if (1) { return 2; }", "TypeError"),
        ("return !1;", "TypeError"),
        ("return 1 && true;", "TypeError"),
        ("return [true];", "TypeError"),
        ("let a=[1]; a[0]=false;", "TypeError"),
        ("let a=[1]; return a[true];", "TypeError"),
        ("let a=[1]; return a[-1];", "IndexError"),
        ("let a=[1]; a[1]=2;", "IndexError"),
        ("return 1/0;", "DivisionByZero"),
        ("return 1%0;", "DivisionByZero"),
        ("return 9223372036854775807+1;", "Overflow"),
        ("return -9223372036854775808/-1;", "Overflow"),
        ("return len(1);", "TypeError"),
        ("return print();", "ArityError"),
        ("fn f(a) { return a; } return f();", "ArityError"),
        ("return missing();", "NameError"),
        ("fn print(a) { return a; }", "NameError"),
    ],
)
def test_reference_reports_semantic_failure(source, kind):
    result = evaluate(source)
    assert result["return_value"] is None
    assert result["error"]["kind"] == kind
    assert result["error"]["line"] > 0
    assert result["error"]["col"] > 0


def test_reference_fuel_bounds_nonterminating_loop():
    result = evaluate("let n=0; while (true) { n=n+1; }", fuel=100)
    assert result["error"]["kind"] == "StepLimit"
    assert result["globals"]["n"] > 0


def test_reference_depth_bounds_recursion():
    result = evaluate("fn f() { return f(); } return f();", max_depth=10)
    assert result["error"]["kind"] == "DepthLimit"


def test_reference_array_limit_is_enforced():
    result = evaluate("return [1,2,3];", max_array=2)
    assert result["error"]["kind"] == "ArrayLimit"


def test_reference_parse_error_is_an_observable_failure():
    result = evaluate("let =;")
    assert result["error"]["kind"] == "SyntaxError"


def test_reference_unary_plus_requires_an_integer():
    assert evaluate("return +1;")["return_value"] == 1
    assert evaluate("return +true;")["error"]["kind"] == "TypeError"


def test_reference_loop_body_can_shadow_its_loop_variable():
    result = evaluate("for i in 0..1 { let i=5; print(i); }")
    assert result["error"] is None
    assert result["output"] == [5]
    assert result["globals"] == {}


def test_reference_index_assignment_uses_binding_after_index_side_effect():
    result = evaluate(
        "let a=[1,2]; fn idx(){ a=[3,4]; return 0; } "
        "a[idx()]=9; return a;"
    )
    assert result["error"] is None
    assert result["return_value"] == [9, 4]


def _generated_programs():
    """Fixed-seed, bounded programs across eight distinct semantic shapes."""
    rng = random.Random(1701)
    programs = []
    for case in range(96):
        a, b, c = (rng.randint(-20, 20) for _ in range(3))
        count = rng.randint(0, 8)
        divisor = rng.choice([-9, -3, -1, 1, 3, 9])
        shapes = [
            f"let x={a}; let y={b}; return (x*y+{c})/{divisor};",
            f"let x={a}; let s=0; for i in 0..{count} {{ s=s+x*i; }} print(s); return s%{divisor};",
            f"let x={a}; fn get() {{ return x; }} fn f(x) {{ return get()+x; }} return f({b});",
            f"let x={abs(a)+1}; let y={abs(b)+1}; while (y!=0) {{ let t=x%y; x=y; y=t; }} return x;",
            f"fn fac(n) {{ if (n<2) {{ return 1; }} return n*fac(n-1); }} return fac({count});",
            f"fn edit(a) {{ a[1]=a[0]+a[2]; return a; }} let a=[{a},{b},{c}]; let b=edit(a); print(a); return b;",
            f"let a={a}; if (a<0) {{ let a={b}; print(a); }} else {{ let a={c}; print(a); }} return a;",
            f"let a=[{a},{b},{c}]; let b=a; for i in 0..len(b) {{ b[i]=b[i]*{divisor}; }} print(a); return b;",
        ]
        programs.append(shapes[case % len(shapes)])
    return programs


@pytest.mark.parametrize("source", _generated_programs(), ids=lambda source: source[:50])
def test_seeded_differential_execution(source):
    # The production evaluator is imported only by this integration test.
    # reference.py never imports it or consults its traces.
    from sonata.language import parse
    from sonata.runtime import execute

    expected = evaluate(source)
    actual = execute(parse(source))
    assert expected["error"] is None, source
    assert actual["error"] is None, source
    assert {field: actual[field] for field in expected} == expected, source
