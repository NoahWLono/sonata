"""Version 1 language contracts: independent behavior, trace, score, and limits."""
from copy import deepcopy

import pytest
from hypothesis import given, settings, strategies as st

from sonata.codec import decode_notes, encode_ast, import_program, compile_program
from sonata.language import SonataSyntaxError, canonical, format_source, parse
from sonata.reference import evaluate
from sonata.runtime import Limits, execute


def both(source, expected, *, inputs=None, limits=None):
    result = execute(parse(source), limits, inputs=inputs)
    reference = evaluate(source, inputs=inputs, max_array=(limits or Limits()).max_array)
    assert result['error'] is None, result
    assert reference['error'] is None, reference
    for field in ('return_value', 'output', 'globals'):
        assert result[field] == reference[field]
    assert result['return_value'] == expected
    return result


def test_assert_success_and_failure_keep_precise_state():
    result = both('let x = 3; assert(x == 3); return x;', 3)
    assert any(e['kind'] == 'branch' and e['data'].get('assertion') and e['data']['taken'] for e in result['trace'])
    source = 'let x = 3;\nassert(x == 4);\nx = 9;'
    failure = execute(parse(source))
    assert failure['error']['kind'] == 'AssertionError'
    assert failure['error']['line'] == 2
    assert failure['globals'] == {'x': 3}
    assert evaluate(source)['error']['kind'] == 'AssertionError'
    assert execute(parse('assert(1);'))['error']['kind'] == 'TypeError'


def test_break_continue_nested_for_while_and_scope_cleanup():
    source = '''let total = 0;
    for i in 0..8 {
        if (i == 1) { continue; }
        if (i == 5) { break; }
        let j = 0;
        while (j < 5) {
            j = j + 1;
            if (j == 2) { continue; }
            if (j == 4) { break; }
            total = total + i;
        }
    }
    return total;'''
    result = both(source, 18)
    assert result['globals'] == {'total': 18}
    controls = [e['data']['control'] for e in result['trace'] if e['kind'] == 'branch' and 'control' in e['data']]
    assert controls.count('continue') == 5
    assert controls.count('break') == 5


@pytest.mark.parametrize('control', ['break', 'continue'])
def test_loop_control_cannot_escape_function_boundary(control):
    source = f'fn f() {{ {control}; }} for i in 0..3 {{ f(); }} return 99;'
    result = execute(parse(source))
    assert result['error']['kind'] == 'ControlFlowError'
    assert result['trace'][-1]['stack'] == ['<main>', 'f']
    assert evaluate(source)['error']['kind'] == 'ControlFlowError'
    assert execute(parse(control + ';'))['error']['kind'] == 'ControlFlowError'


def test_function_own_loop_does_not_consume_callers_continue():
    both('fn f() { for j in 0..3 { break; } return 2; } let n = 0; for i in 0..3 { n = n + f(); continue; } return n;', 6)


def test_continuing_loop_is_still_bounded():
    result = execute(parse('while (true) { continue; }'), Limits(max_steps=30))
    assert result['error']['kind'] == 'StepLimit'
    assert result['instructions'] == 30


@pytest.mark.parametrize(('expression', 'expected'), [
    ('abs(-3)', 3), ('min(2, -7)', -7), ('max(2, -7)', 2),
    ('clamp(-2, 0, 5)', 0), ('clamp(3, 0, 5)', 3), ('clamp(9, 0, 5)', 5),
    ('sum([])', 0), ('sum([3, -1, 8])', 10),
    ('range(-2, 3)', [-2,-1,0,1,2]), ('range(3, 1)', []),
    ('repeat(7, 3)', [7,7,7]), ('repeat(-1, 0)', []),
])
def test_bounded_standard_library(expression, expected):
    both(f'return {expression};', expected)


@pytest.mark.parametrize(('expression', 'kind'), [
    ('abs(-9223372036854775808)', 'Overflow'), ('sum([9223372036854775807, 1, -1])', 'Overflow'),
    ('clamp(3, 8, 1)', 'ValueError'), ('repeat(2, -1)', 'ValueError'),
    ('repeat(true, 1)', 'TypeError'), ('range(0, true)', 'TypeError'),
    ('sum(1)', 'TypeError'), ('max(1)', 'ArityError'),
    ('range(-9223372036854775808, 9223372036854775807)', 'ArrayLimit'),
    ('repeat(1, 9223372036854775807)', 'ArrayLimit'),
])
def test_standard_library_errors(expression, kind):
    source = f'return {expression};'
    assert execute(parse(source))['error']['kind'] == kind
    assert evaluate(source)['error']['kind'] == kind


def test_array_builtins_account_for_element_work_and_limits():
    assert execute(parse('return range(0, 4);'), Limits(max_array=3))['error']['kind'] == 'ArrayLimit'
    assert execute(parse('return repeat(1, 4);'), Limits(max_steps=5))['error']['kind'] == 'StepLimit'
    both('return range(2, 2);', [], limits=Limits(max_array=0))


def test_fixtures_are_validated_copied_and_traced():
    inputs = [[1,2], 8, True]
    before = deepcopy(inputs)
    source = 'let a = input(0); a[0] = 99; assert(input(2)); print(input(0)); return sum(a) + input(1);'
    result = both(source, 109, inputs=inputs)
    assert inputs == before
    assert result['output'] == [[1,2]]
    reads = [e for e in result['trace'] if e['kind'] == 'read' and 'input' in e['data']]
    assert [e['data']['input'] for e in reads] == [0,2,0,1]
    assert result == execute(parse(source), inputs=inputs)


@pytest.mark.parametrize('inputs', [{}, [None], [1.1], ['1'], [[True]], [[[1]]], [2**63], [object()], [0]*4097, [list(range(256))]*257])
def test_invalid_fixture_values_fail_before_execution(inputs):
    result = execute(parse('print(1);'), inputs=inputs)
    assert result['error']['kind'] == 'InputError'
    assert result['output'] == []
    assert evaluate('print(1);', inputs=inputs)['error']['kind'] == 'InputError'


@pytest.mark.parametrize(('source', 'kind'), [('return input(0);','IndexError'), ('return input(-1);','IndexError'), ('return input(true);','TypeError'), ('return input();','ArityError')])
def test_input_index_contract(source, kind):
    assert execute(parse(source))['error']['kind'] == kind
    assert evaluate(source)['error']['kind'] == kind


@pytest.mark.parametrize('name', ['input', 'abs', 'min', 'max', 'clamp', 'sum', 'range', 'repeat'])
def test_builtins_cannot_be_redeclared(name):
    source = f'fn {name}() {{ return 1; }}'
    assert execute(parse(source))['error']['kind'] == 'NameError'
    assert evaluate(source)['error']['kind'] == 'NameError'


def test_new_syntax_ast_midi_roundtrip_and_input_behavior(tmp_path):
    source = 'let total = 0; for i in 0..input(0) { if (i == 2) { continue; } if (i == 5) { break; } total = total + i; } assert(total == 8); return total;'
    ast = parse(source)
    assert canonical(parse(format_source(ast))) == canonical(ast)
    assert canonical(decode_notes(encode_ast(ast))) == canonical(ast)
    path = tmp_path / 'v1.mid'
    compile_program(ast, path)
    rebuilt = import_program(path)
    assert canonical(rebuilt) == canonical(ast)
    assert execute(rebuilt, inputs=[10])['return_value'] == 8


@settings(max_examples=40, derandomize=True)
@given(st.lists(st.integers(-1000, 1000), max_size=20), st.integers(-1000, 1000))
def test_randomized_builtin_and_control_reference(values, threshold):
    source = 'let a = input(0); let total = 0; for i in 0..len(a) { if (a[i] < input(1)) { continue; } total = total + a[i]; } assert(total <= sum(repeat(1000, len(a)))); return total;'
    both(source, sum(x for x in values if x >= threshold), inputs=[values, threshold])


def test_oversized_fixture_arrays_and_host_subclasses_are_rejected():
    class ForeignInt(int):
        pass
    for inputs in ([list(range(257))], [ForeignInt(1)]):
        result = execute(parse('return 0;'), inputs=inputs)
        assert result['error']['kind'] == 'InputError'
    assert evaluate('return 0;', max_array=256, inputs=[list(range(257))])['error']['kind'] == 'InputError'


def test_fixture_validation_caps_are_inclusive():
    result = execute(parse('return len(input(0));'), Limits(max_array=4096), inputs=[list(range(4096))] * 16)
    assert result['error'] is None
    assert result['return_value'] == 4096
    assert execute(parse('return input(4095);'), inputs=[7]*4096)['return_value'] == 7


def test_builtin_arguments_evaluate_once_in_left_to_right_order():
    source = 'let x = 0; fn next() { x = x + 1; return x; } let a = range(next(), next() + 2); return a;'
    result = both(source, [1, 2, 3])
    assert result['globals']['x'] == 2


def test_new_keywords_cannot_be_variables_or_parameters():
    for keyword in ('assert', 'break', 'continue', 'import'):
        with pytest.raises(SonataSyntaxError):
            parse(f'let {keyword} = 1;')
        with pytest.raises(SonataSyntaxError):
            parse(f'fn f({keyword}) {{ return 1; }}')


def test_break_does_not_leak_past_function_own_completed_loop():
    source = 'fn f() { for i in 0..1 { break; } break; } for j in 0..3 { f(); }'
    assert execute(parse(source))['error']['kind'] == 'ControlFlowError'
    assert evaluate(source)['error']['kind'] == 'ControlFlowError'
