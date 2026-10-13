import sys
import pytest
from sonata.music import sonify


def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)


def sum_values(n):
    total=0
    for i in range(n):
        total+=i
    return total


def fail():
    denominator=0
    return 1//denominator


def test_callable_adapter_records_recursion_and_return():
    from sonata.python_trace import trace_callable, validate_trace_bundle
    result=trace_callable(fibonacci,5)
    assert result['return_value']==5 and result['error'] is None
    assert result['schema']=='sonata-python-trace' and result['version']==1
    assert max(e['depth'] for e in result['trace'])==5
    assert {e['kind'] for e in result['trace']} >= {'call','return','statement'}
    assert len(sonify(result['trace'],profile={}))>0
    assert validate_trace_bundle(result)==result
    assert [e['id'] for e in result['trace']]==list(range(len(result['trace'])))
    assert result==trace_callable(fibonacci,5)


def test_adapter_observes_assignments_and_accurate_snapshot_values():
    from sonata.python_trace import trace_callable
    result=trace_callable(sum_values,5)
    assert result['return_value']==10
    changes=[e for e in result['trace'] if e['kind']=='assign' and e['data']['name']=='total']
    assert [e['data']['value'] for e in changes]==[1,3,6,10]
    assert changes[-1]['variables']['total']==10


def test_adapter_errors_preserve_innermost_locals_and_restore_tracer():
    from sonata.python_trace import trace_callable
    previous=sys.gettrace()
    result=trace_callable(fail)
    assert sys.gettrace() is previous
    assert result['error']['kind']=='ZeroDivisionError'
    assert result['trace'][-1]['kind']=='error'
    assert result['trace'][-1]['variables']['denominator']==0


def test_adapter_bounds_traces_and_recursion():
    from sonata.python_trace import trace_callable
    result=trace_callable(fibonacci,20,max_events=12)
    assert result['error']['kind']=='TraceLimit'
    assert len(result['trace'])<=13
    result=trace_callable(fibonacci,20,max_depth=3)
    assert result['error']['kind']=='DepthLimit'
    assert max(e['depth'] for e in result['trace'])<=3


def test_adapter_is_explicit_about_unsupported_locals_and_return():
    from sonata.python_trace import trace_callable
    def has_object():
        opaque=object()
        value=3
        return value
    result=trace_callable(has_object)
    assert result['return_value']==3
    assert any('opaque' in e['data'].get('omitted_variables',[]) for e in result['trace'])
    def returns_object(): return object()
    result=trace_callable(returns_object)
    assert result['error']['kind']=='UnsupportedValue'


def test_adapter_rejects_async_and_untrusted_trace_shape():
    from sonata.python_trace import trace_callable, validate_trace_bundle
    async def async_function(): return 1
    with pytest.raises(ValueError): trace_callable(async_function)
    with pytest.raises(ValueError): trace_callable('print(123)')
    result=trace_callable(sum_values,3)
    result['trace'][0]['depth']=-1
    with pytest.raises(ValueError): validate_trace_bundle(result)


def test_adapter_preserves_an_existing_debugger():
    from sonata.python_trace import trace_callable
    def active(frame,event,arg): return active
    previous=sys.gettrace()
    try:
        sys.settrace(active)
        with pytest.raises(ValueError,match='tracer'): trace_callable(sum_values,3)
        assert sys.gettrace() is active
    finally: sys.settrace(previous)


def test_nested_exception_keeps_innermost_failure_context():
    from sonata.python_trace import trace_callable
    def outer():
        def inner():
            denominator=0
            return 1//denominator
        return inner()
    result=trace_callable(outer)
    assert result['error']['kind']=='ZeroDivisionError'
    assert result['trace'][-1]['function']=='inner'
    assert result['trace'][-1]['variables']=={'denominator':0}


def test_bundle_rejects_extra_unbounded_data():
    from sonata.python_trace import trace_callable,validate_trace_bundle
    bundle=trace_callable(sum_values,3)
    bundle['trace'][0]['extra']={'nested':[[1]]}
    with pytest.raises(ValueError): validate_trace_bundle(bundle)


def test_reraised_exception_uses_its_own_origin_not_last_handled_error():
    from sonata.python_trace import trace_callable
    def subject():
        error=ValueError('original')
        try:
            raise error
        except ValueError:
            try:
                1//0
            except ZeroDivisionError:
                pass
            raise error
    bundle=trace_callable(subject)
    origin=next(e for e in bundle['trace'] if e['kind']=='error' and e['data']['kind']=='ValueError')
    assert bundle['error']['kind']=='ValueError'
    assert bundle['error']['line']==origin['line']
    assert bundle['trace'][-1]['data']['kind']=='ValueError'
    assert bundle['trace'][-1]['line']==origin['line']


def test_finally_during_exception_unwind_is_not_a_successful_return():
    from sonata.python_trace import trace_callable
    def subject():
        try:
            return 1//0
        finally:
            cleanup=1
    bundle=trace_callable(subject)
    assert bundle['error']['kind']=='ZeroDivisionError'
    assert not any(e['kind']=='return' for e in bundle['trace'])
    def override():
        try:
            return 1//0
        finally:
            return None
    bundle=trace_callable(override)
    assert bundle['error'] is None and bundle['return_value'] is None
    assert bundle['trace'][-1]['kind']=='return'


def test_bundle_error_location_fields_are_validated_before_copy():
    from sonata.python_trace import trace_callable, validate_trace_bundle
    bundle=trace_callable(fail)
    bundle['trace'][-1]['data']['line']={'not':'an integer'}
    with pytest.raises(ValueError): validate_trace_bundle(bundle)


def test_adapter_declares_its_cpython_dependency(monkeypatch):
    from types import SimpleNamespace
    from sonata.python_trace import trace_callable
    monkeypatch.setattr(sys,'implementation',SimpleNamespace(name='another-python'))
    with pytest.raises(ValueError,match='CPython'): trace_callable(sum_values,3)
