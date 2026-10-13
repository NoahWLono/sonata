"""Explicit tracing of trusted synchronous Python functions.

This adapter is an observation tool, not a sandbox. The callable retains all
Python privileges and its own side effects. Limits bound recorded Python trace
events, not uninterruptible native calls, threads, or deliberately hostile code.
"""

from copy import deepcopy
import dis
import inspect
from pathlib import Path
import sys
import types


class _AdapterFault(RuntimeError):
    def __init__(self, kind, message):
        self.kind = kind
        super().__init__(message)


def _value(value, max_array=256):
    if type(value) is bool or (type(value) is int and -(2**63) <= value < 2**63):
        return value
    if type(value) in (list, tuple) and len(value) <= max_array and all(type(v) is int and -(2**63) <= v < 2**63 for v in value):
        return list(value)
    raise ValueError("Expected signed 64-bit integer, Boolean, or bounded integer array")


def _bound(name, value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")


def trace_callable(function, *args, max_events=10_000, max_depth=32,
                   max_array=256, max_values=2_000_000, **kwargs):
    """Observe a trusted function and same-file descendant calls in this thread.

    Calls, source-line visits, local variable changes, returns, and exceptions
    become SONATA-compatible events. Values outside the small supported type
    set are named in `omitted_variables`; no repr()/user conversion is called.
    Source statements are line visits, not inferred Python branch decisions.
    """
    if sys.implementation.name != "cpython":
        raise ValueError("The Python trace adapter requires CPython return-opcode semantics")
    if not isinstance(function, types.FunctionType) or inspect.iscoroutinefunction(function) or inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
        raise ValueError("trace_callable needs a trusted synchronous Python function")
    if sys.gettrace() is not None:
        raise ValueError("An existing Python tracer is active; stop it before tracing")
    for name, value, low, high in (("max_events", max_events, 1, 100_000), ("max_depth", max_depth, 1, 128),
                                   ("max_array", max_array, 0, 4096), ("max_values", max_values, 1, 10_000_000)):
        _bound(name, value, low, high)
    filename = function.__code__.co_filename
    frames, stack, trace = {}, [], []
    observed_exceptions = {}
    value_cost = 0
    stopped_fault = None
    error, returned = None, None
    error_template = None
    last_context = {"line": function.__code__.co_firstlineno, "variables": {}, "stack": [function.__name__]}

    def snapshot(frame):
        variables, omitted = {}, []
        local_values = frame.f_locals
        if len(local_values) > 1024:
            raise _AdapterFault("TraceLimit", "Local variable count exceeds 1024")
        for name, value in sorted(local_values.items()):
            if len(name) > 128:
                raise _AdapterFault("TraceLimit", "Local variable name exceeds 128 characters")
            try:
                variables[name] = _value(value, max_array)
            except ValueError:
                omitted.append(name)
        return variables, omitted

    def emit(event_kind, frame, variables, omitted, *, line=None, **data):
        nonlocal value_cost, last_context
        names = [f.f_code.co_name for f in stack]
        last_context = {"line": line if line is not None else frame.f_lineno, "variables": variables, "stack": names}
        if len(trace) >= max_events:
            raise _AdapterFault("TraceLimit", "Python trace event limit exceeded")
        cost = 1 + len(names) + len(omitted) + sum(1 + (len(v) if type(v) is list else 1) for v in variables.values())
        if value_cost + cost > max_values:
            raise _AdapterFault("TraceLimit", "Python trace snapshot budget exceeded")
        value_cost += cost
        if omitted:
            data["omitted_variables"] = omitted
        trace.append({"id": len(trace), "kind": event_kind, "line": last_context["line"], "col": 1,
                      "depth": len(names), "function": names[-1], "data": deepcopy(data),
                      "variables": deepcopy(variables), "stack": ["<python>", *names]})

    def changes(frame, variables, omitted):
        state = frames[frame]
        for name, value in variables.items():
            old = state["variables"].get(name)
            if name not in state["variables"]:
                emit("declare", frame, variables, omitted, line=state["line"], name=name, value=value)
            elif type(value) is not type(old) or value != old:
                emit("assign", frame, variables, omitted, line=state["line"], name=name, value=value)
        state["variables"] = variables

    def observe(frame, event, arg):
        nonlocal stopped_fault
        try:
            if event == "call":
                if frame.f_code is not function.__code__ and (frame.f_code.co_filename != filename or frame.f_back not in frames):
                    return None
                if frame.f_code.co_flags & (inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR):
                    return None
                if len(stack) >= max_depth:
                    raise _AdapterFault("DepthLimit", "Python trace recursion limit exceeded")
                stack.append(frame)
                variables, omitted = snapshot(frame)
                frames[frame] = {"variables": variables, "line": frame.f_lineno, "exception": False}
                emit("call", frame, variables, omitted, name=frame.f_code.co_name)
                return observe
            if frame not in frames:
                return None
            variables, omitted = snapshot(frame)
            if event == "line":
                changes(frame, variables, omitted)
                frames[frame]["exception"] = False
                frames[frame]["line"] = frame.f_lineno
                emit("statement", frame, variables, omitted, statement="python_line")
            elif event == "exception":
                frames[frame]["exception"] = True
                if id(arg[1]) not in observed_exceptions:
                    emit("error", frame, variables, omitted, kind=arg[0].__name__, message=str(arg[1])[:1024])
                    observed_exceptions[id(arg[1])] = (arg[1], trace[-1])
            elif event == "return":
                # A trace return with arg=None can be exception unwinding.
                # Finally suites have line events too, so a line visit cannot
                # establish that an earlier exception was handled. CPython's
                # last opcode distinguishes real return from RERAISE/CALL/etc.
                opcode = dis.opname[frame.f_code.co_code[frame.f_lasti]]
                if opcode in {"RETURN_VALUE", "RETURN_CONST", "INSTRUMENTED_RETURN_VALUE", "INSTRUMENTED_RETURN_CONST"}:
                    changes(frame, variables, omitted)
                    try:
                        value = None if arg is None else _value(arg, max_array)
                    except ValueError as exc:
                        raise _AdapterFault("UnsupportedValue", "Python return value is outside the trace value types") from exc
                    emit("return", frame, variables, omitted, value=value)
                del frames[frame]
                stack.pop()
            return observe
        except _AdapterFault as fault:
            stopped_fault = fault
            raise

    try:
        sys.settrace(observe)
        result = function(*args, **kwargs)
        if stopped_fault is not None:
            raise stopped_fault
        returned = None if result is None else _value(result, max_array)
    except _AdapterFault as exc:
        error = {"kind": exc.kind, "message": str(exc), "line": last_context["line"], "col": 1}
    except Exception as exc:
        # The innermost observed error already contains the correct local state.
        observed = observed_exceptions.get(id(exc))
        error_event = observed[1] if observed is not None else None
        error_template = error_event
        error = {"kind": type(exc).__name__, "message": str(exc)[:1024],
                 "line": error_event["line"] if error_event else last_context["line"], "col": 1}
    finally:
        sys.settrace(None)
        frames.clear()
        stack.clear()
        observed_exceptions.clear()
    if error_template is not None and trace[-1] is not error_template:
        final_error = deepcopy(error_template)
        final_error["id"] = len(trace)
        trace.append(final_error)
    elif error and (not trace or trace[-1]["kind"] != "error" or trace[-1]["data"].get("kind") != error["kind"]):
        names = last_context["stack"] or [function.__name__]
        trace.append({"id": len(trace), "kind": "error", "line": error["line"], "col": 1,
                      "depth": len(names), "function": names[-1], "stack": ["<python>", *names],
                      "variables": deepcopy(last_context["variables"]), "data": dict(error)})
    try:
        source_lines, start_line = inspect.getsourcelines(function)
        source = "".join(source_lines)
    except (OSError, TypeError):
        source, start_line = "", function.__code__.co_firstlineno
    return {"schema": "sonata-python-trace", "version": 1, "source": source,
            "source_start_line": start_line, "filename": Path(filename).name,
            "return_value": returned, "error": error, "trace": trace}


def validate_trace_bundle(bundle):
    """Validate a loaded adapter bundle before sending its trace to sonify()."""
    fields = {"schema", "version", "source", "source_start_line", "filename", "return_value", "error", "trace"}
    if type(bundle) is not dict or set(bundle) != fields or bundle.get("schema") != "sonata-python-trace" or type(bundle.get("version")) is not int or bundle["version"] != 1:
        raise ValueError("Unsupported Python trace bundle schema/version")
    if type(bundle["source"]) is not str or len(bundle["source"]) > 200_000 or type(bundle["filename"]) is not str or len(bundle["filename"]) > 1024:
        raise ValueError("Invalid trace source information")
    _bound("source_start_line", bundle["source_start_line"], 1, 100_000_000)
    if bundle["return_value"] is not None:
        _value(bundle["return_value"], 4096)
    trace = bundle["trace"]
    if type(trace) is not list or len(trace) > 100_001:
        raise ValueError("Trace event limit exceeded")
    total = 0
    for index, event in enumerate(trace):
        if type(event) is not dict or set(event) != {"id", "kind", "line", "col", "depth", "function", "data", "variables", "stack"} or type(event.get("id")) is not int or event["id"] != index:
            raise ValueError("Trace event IDs must be contiguous integers")
        for key in ("line", "col"):
            _bound(key, event.get(key), 1, 100_000_000)
        _bound("depth", event.get("depth"), 1, 128)
        if event.get("kind") not in {"call", "return", "statement", "declare", "assign", "error"}:
            raise ValueError("Unknown Python trace event kind")
        stack = event.get("stack")
        if type(stack) is not list or len(stack) != event["depth"]+1 or any(type(n) is not str or len(n)>128 for n in stack) or event.get("function") != stack[-1]:
            raise ValueError("Invalid Python trace call stack")
        variables, data = event.get("variables"), event.get("data")
        if type(variables) is not dict or len(variables)>1024 or type(data) is not dict:
            raise ValueError("Invalid trace variables or data")
        for name, value in variables.items():
            if type(name) is not str or not 1 <= len(name) <= 128:
                raise ValueError("Invalid trace variable name")
            _value(value, 4096)
            total += 1 + (len(value) if type(value) is list else 1)
        if set(data)-{"name", "value", "statement", "kind", "message", "line", "col", "omitted_variables"}:
            raise ValueError("Unsupported trace event data")
        if "value" in data and data["value"] is not None:
            _value(data["value"], 4096)
            total += len(data["value"]) if type(data["value"]) is list else 1
        for key in ("line", "col"):
            if key in data:
                _bound(key, data[key], 1, 100_000_000)
        for key in ("name", "statement", "kind", "message"):
            if key in data and (type(data[key]) is not str or len(data[key])>1024):
                raise ValueError("Invalid trace event text")
        omitted = data.get("omitted_variables", [])
        if type(omitted) is not list or len(omitted)>1024 or any(type(n) is not str or len(n)>128 for n in omitted):
            raise ValueError("Invalid omitted variable list")
        total += len(stack) + len(omitted) + 1
        if total > 10_000_000:
            raise ValueError("Trace snapshot value budget exceeded")
    error = bundle["error"]
    if error is not None:
        if type(error) is not dict or set(error) != {"kind", "message", "line", "col"} or any(type(error[k]) is not str or len(error[k])>1024 for k in ("kind", "message")):
            raise ValueError("Invalid trace error")
        for key in ("line", "col"):
            _bound(key, error[key], 1, 100_000_000)
    return deepcopy(bundle)
