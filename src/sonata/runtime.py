"""A bounded tree-walking interpreter with deterministic, complete trace records."""

from copy import deepcopy
from dataclasses import dataclass
import math
import time

from .language import SonataSyntaxError, validate_ast

BUILTINS = {"print": 1, "len": 1, "input": 1, "abs": 1, "min": 2,
            "max": 2, "clamp": 3, "sum": 1, "range": 2, "repeat": 2}


@dataclass(frozen=True)
class Limits:
    max_steps: int = 10_000
    max_depth: int = 32
    max_array: int = 256
    timeout_seconds: float | None = None
    max_trace_values: int = 2_000_000

    def __post_init__(self):
        for name, minimum, maximum in [("max_steps", 1, 1_000_000), ("max_depth", 1, 128), ("max_array", 0, 4096), ("max_trace_values", 1, 10_000_000)]:
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
        if self.timeout_seconds is not None and (type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds) or self.timeout_seconds < 0):
            raise ValueError("timeout_seconds must be finite and nonnegative")


class _Fault(Exception):
    def __init__(self, kind, message, node):
        self.kind, self.message, self.node = kind, message, node
        self.context = None


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _LoopControl(Exception):
    def __init__(self, kind):
        self.kind = kind


class _Machine:
    def __init__(self, limits):
        self.limits = limits
        self.globals, self.scopes = {}, []
        self.scopes.append(self.globals)
        self.stack = ["<main>"]
        self.functions = {}
        self.trace, self.output = [], []
        self.instructions = 0
        self.trace_values = 0
        self.nesting = 0
        self.started = time.monotonic()
        self.current = {"line": 1, "col": 1}
        self.inputs = []
        self.loop_depth = 0

    def prepare_inputs(self, inputs):
        """Copy and validate a bounded host fixture before any source runs."""
        if inputs is None:
            return
        if type(inputs) is not list or len(inputs) > 4096:
            raise _Fault("InputError", "Inputs must be a list of at most 4096 values", self.current)
        count = 0
        for value in inputs:
            if type(value) is list:
                count += len(value)
                valid = len(value) <= self.limits.max_array and all(type(item) is int and -(2**63) <= item < 2**63 for item in value)
            else:
                count += 1
                valid = type(value) is bool or (type(value) is int and -(2**63) <= value < 2**63)
            if not valid or count > 65536:
                raise _Fault("InputError", "Inputs require bounded int64, Boolean, or integer-array values (65536 value slots maximum)", self.current)
        self.inputs = deepcopy(inputs)

    def tick(self, node):
        self.current = node
        if self.instructions >= self.limits.max_steps:
            raise _Fault("StepLimit", "Instruction limit exceeded", node)
        if self.limits.timeout_seconds is not None and time.monotonic() - self.started >= self.limits.timeout_seconds:
            raise _Fault("Timeout", "Execution timeout exceeded", node)
        self.instructions += 1

    def emit(self, event_kind, node, **data):
        variables = {}
        for scope in self.scopes:
            variables.update(scope)
        cost = 1 + len(self.stack) + sum(1 + (len(value) if type(value) is list else 1) for value in variables.values())
        cost += sum(1 + (len(value) if type(value) is list else 1) for value in data.values())
        if event_kind != "error" and self.trace_values + cost > self.limits.max_trace_values:
            raise _Fault("TraceLimit", "Trace snapshot value budget exceeded", node)
        self.trace_values += cost
        self.trace.append({"id": len(self.trace), "kind": event_kind, "line": node.get("line", 1), "col": node.get("col", 1),
                           "depth": len(self.stack) - 1, "function": self.stack[-1], "data": deepcopy(data),
                           "variables": deepcopy(variables), "stack": list(self.stack)})

    def scope(self, name, node):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope
        raise _Fault("NameError", f"Undefined variable {name!r}", node)

    def integer(self, value, node):
        if type(value) is not int:
            raise _Fault("TypeError", "Expected integer", node)
        if not -(2**63) <= value < 2**63:
            raise _Fault("Overflow", "Integer exceeds signed 64-bit range", node)
        return value

    def boolean(self, value, node):
        if type(value) is not bool:
            raise _Fault("TypeError", "Expected Boolean", node)
        return value

    def array(self, value, node):
        if type(value) is not list:
            raise _Fault("TypeError", "Expected integer array", node)
        return value

    def offset(self, value, array, node):
        index = self.integer(value, node)
        if not 0 <= index < len(array):
            raise _Fault("IndexError", "Array index out of bounds", node)
        return index

    def capture(self, fault):
        if fault.context is None:
            variables = {}
            for scope in self.scopes:
                variables.update(scope)
            fault.context = (deepcopy(variables), list(self.stack))

    def expression(self, node):
        if self.nesting >= 128:
            raise _Fault("DepthLimit", "Combined execution nesting limit exceeded", node)
        self.nesting += 1
        try:
            return self.evaluate(node)
        finally:
            self.nesting -= 1

    def evaluate(self, node):
        self.tick(node)
        kind = node["kind"]
        if kind == "int":
            return self.integer(node["value"], node)
        if kind == "bool":
            return self.boolean(node["value"], node)
        if kind == "array":
            if len(node["items"]) > self.limits.max_array:
                raise _Fault("ArrayLimit", "Array length limit exceeded", node)
            return [self.integer(self.expression(item), item) for item in node["items"]]
        if kind == "index":
            value = self.array(self.expression(node["value"]), node)
            index = self.offset(self.expression(node["index"]), value, node)
            self.emit("read", node, index=index, value=value[index])
            return value[index]
        if kind == "unary":
            if node["op"] == "-" and node["value"]["kind"] == "int" and node["value"]["value"] == 2**63:
                self.tick(node["value"])
                return -(2**63)
            value = self.expression(node["value"])
            if node["op"] == "!":
                return not self.boolean(value, node)
            value = self.integer(value, node)
            return self.integer(-value if node["op"] == "-" else value, node)
        if kind == "var":
            value = deepcopy(self.scope(node["name"], node)[node["name"]])
            self.emit("read", node, name=node["name"], value=value)
            return value
        if kind == "binary":
            op = node["op"]
            left = self.expression(node["left"])
            if op in {"&&", "||"}:
                left = self.boolean(left, node)
                evaluate_right = (op == "&&" and left) or (op == "||" and not left)
                self.emit("branch", node, operator=op, taken=evaluate_right, short_circuit=not evaluate_right)
                if not evaluate_right:
                    return left
                return self.boolean(self.expression(node["right"]), node)
            right = self.expression(node["right"])
            if op in {"==", "!="}:
                if type(left) is not type(right):
                    raise _Fault("TypeError", "Equality requires matching types", node)
                return left == right if op == "==" else left != right
            left, right = self.integer(left, node), self.integer(right, node)
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "+":
                value = left + right
            elif op == "-":
                value = left - right
            elif op == "*":
                value = left * right
            elif op in {"/", "%"}:
                if right == 0:
                    raise _Fault("DivisionByZero", "Division or remainder by zero", node)
                quotient = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
                value = quotient if op == "/" else left - quotient * right
            else:
                raise _Fault("TypeError", f"Unsupported operator {op!r}", node)
            return self.integer(value, node)
        if kind == "call":
            return self.call(node)
        raise _Fault("TypeError", f"Unknown expression {kind!r}", node)

    def call(self, node):
        name = node["name"]
        if name in BUILTINS:
            if len(node["args"]) != BUILTINS[name]:
                raise _Fault("ArityError", f"{name} expects {BUILTINS[name]} arguments", node)
            values = [self.expression(arg) for arg in node["args"]]
            value = values[0]
            if name == "len":
                return len(self.array(value, node))
            if name == "print":
                self.output.append(deepcopy(value))
                self.emit("output", node, value=value)
                return value
            if name == "input":
                index = self.offset(value, self.inputs, node)
                value = deepcopy(self.inputs[index])
                self.emit("read", node, input=index, value=value)
                return value
            if name == "sum":
                result = 0
                for element in self.array(value, node):
                    self.tick(node)
                    result = self.integer(result + element, node)
                return result
            values = [self.integer(item, node) for item in values]
            if name == "abs":
                return self.integer(abs(values[0]), node)
            if name in {"min", "max"}:
                return min(values) if name == "min" else max(values)
            if name == "clamp":
                value, lower, upper = values
                if lower > upper:
                    raise _Fault("ValueError", "clamp lower bound exceeds upper bound", node)
                return min(max(value, lower), upper)
            first, second = values
            count = max(0, second - first) if name == "range" else second
            if count < 0:
                raise _Fault("ValueError", "repeat count must be nonnegative", node)
            if count > self.limits.max_array:
                raise _Fault("ArrayLimit", "Array length limit exceeded", node)
            result = []
            for index in range(count):
                self.tick(node)
                result.append(first + index if name == "range" else first)
            return result
        if name not in self.functions:
            raise _Fault("NameError", f"Undefined function {name!r}", node)
        function = self.functions[name]
        if len(node["args"]) != len(function["params"]):
            raise _Fault("ArityError", f"{name} expects {len(function['params'])} arguments", node)
        if len(self.stack) - 1 >= self.limits.max_depth:
            raise _Fault("DepthLimit", "Function call depth limit exceeded", node)
        values = [self.expression(arg) for arg in node["args"]]
        previous, previous_loop_depth = self.scopes, self.loop_depth
        self.loop_depth = 0
        self.scopes = [self.globals, dict(zip(function["params"], deepcopy(values)))]
        self.stack.append(name)
        try:
            self.emit("call", node, name=name, arguments=values)
            try:
                self.block(function["body"], scoped=False)
            except _Return as returned:
                return deepcopy(returned.value)
            self.emit("return", function, value=0, implicit=True)
            return 0
        except _Fault as fault:
            self.capture(fault)
            raise
        finally:
            self.stack.pop()
            self.scopes = previous
            self.loop_depth = previous_loop_depth

    def block(self, body, scoped=True):
        if self.nesting >= 128:
            raise _Fault("DepthLimit", "Combined execution nesting limit exceeded", self.current)
        self.nesting += 1
        if scoped:
            self.scopes.append({})
        try:
            for node in body:
                self.statement(node)
        except _Fault as fault:
            self.capture(fault)
            raise
        finally:
            self.nesting -= 1
            if scoped:
                self.scopes.pop()

    def statement(self, node):
        self.tick(node)
        self.emit("statement", node, statement=node["kind"])
        kind = node["kind"]
        if kind == "assert":
            condition = self.boolean(self.expression(node["condition"]), node)
            self.emit("branch", node, taken=condition, assertion=True)
            if not condition:
                raise _Fault("AssertionError", "Assertion failed", node)
        elif kind in {"break", "continue"}:
            if not self.loop_depth:
                raise _Fault("ControlFlowError", f"{kind} requires a loop in the current function", node)
            self.emit("branch", node, taken=True, control=kind)
            raise _LoopControl(kind)
        elif kind == "let":
            name, value = node["name"], self.expression(node["value"])
            if name in self.scopes[-1]:
                raise _Fault("NameError", f"Variable {name!r} already declared in this scope", node)
            self.scopes[-1][name] = deepcopy(value)
            self.emit("declare", node, name=name, value=value)
        elif kind == "assign":
            target = node["target"]
            value = self.expression(node["value"])
            if target["kind"] == "var":
                name = target["name"]
                scope = self.scope(name, node)
                if type(value) is not type(scope[name]):
                    raise _Fault("TypeError", "Assignment must preserve variable type", node)
                scope[name] = deepcopy(value)
                self.emit("assign", node, name=name, value=value)
            elif target["kind"] == "index" and target["value"]["kind"] == "var":
                name = target["value"]["name"]
                position = self.expression(target["index"])
                array = self.array(self.scope(name, node)[name], node)
                index = self.offset(position, array, node)
                array[index] = self.integer(value, node)
                self.emit("assign", node, name=name, index=index, value=value)
            else:
                raise _Fault("TypeError", "Array assignment requires a named array", node)
        elif kind == "expr_stmt":
            self.expression(node["value"])
        elif kind == "return":
            value = self.expression(node["value"])
            self.emit("return", node, value=value)
            raise _Return(value)
        elif kind == "fn":
            self.emit("declare", node, name=node["name"], function=True)
        elif kind == "if":
            condition = self.boolean(self.expression(node["condition"]), node)
            self.emit("branch", node, taken=condition)
            self.block(node["then"] if condition else node["else"])
        elif kind == "while":
            iteration = 0
            while True:
                self.tick(node)
                condition = self.boolean(self.expression(node["condition"]), node)
                self.emit("loop", node, taken=condition, iteration=iteration)
                if not condition:
                    break
                if self.loop_body(node["body"]) == "break":
                    break
                iteration += 1
        elif kind == "for":
            start = self.integer(self.expression(node["start"]), node)
            end = self.integer(self.expression(node["end"]), node)
            self.scopes.append({})
            try:
                iteration = 0
                value = start
                while True:
                    self.tick(node)
                    taken = value < end
                    self.emit("loop", node, taken=taken, iteration=iteration, value=value, name=node["name"])
                    if not taken:
                        break
                    self.scopes[-1][node["name"]] = value
                    self.emit("assign", node, name=node["name"], value=value)
                    if self.loop_body(node["body"]) == "break":
                        break
                    iteration += 1
                    value += 1
            except _Fault as fault:
                self.capture(fault)
                raise
            finally:
                self.scopes.pop()
        else:
            raise _Fault("TypeError", f"Unknown statement {kind!r}", node)

    def loop_body(self, body):
        self.loop_depth += 1
        try:
            self.block(body)
        except _LoopControl as control:
            return control.kind
        finally:
            self.loop_depth -= 1


def execute(program: dict, limits: Limits | None = None, inputs=None) -> dict:
    machine = _Machine(limits or Limits())
    value, error = None, None
    try:
        try:
            validate_ast(program)
        except SonataSyntaxError as syntax:
            raise _Fault("InvalidAST", syntax.message, {"line": syntax.line, "col": syntax.col}) from None
        machine.prepare_inputs(inputs)
        for node in program["body"]:
            if node["kind"] == "import":
                raise _Fault("ImportError", "Resolve imports with sonata.loader.load_program before execution", node)
            if node["kind"] == "fn":
                name = node["name"]
                if name in machine.functions or name in BUILTINS:
                    raise _Fault("NameError", f"Function {name!r} already defined or reserved", node)
                if len(node["params"]) != len(set(node["params"])):
                    raise _Fault("NameError", "Duplicate function parameter", node)
                machine.functions[name] = node
        machine.block(program["body"], scoped=False)
    except _Return as returned:
        value = returned.value
    except _Fault as fault:
        error = {"kind": fault.kind, "message": fault.message, "line": fault.node.get("line", 1), "col": fault.node.get("col", 1)}
        machine.emit("error", fault.node, **error)
        if fault.context is not None:
            variables, stack = fault.context
            machine.trace[-1].update(variables=variables, stack=stack, depth=len(stack) - 1, function=stack[-1])
    except RecursionError:
        error = {"kind": "DepthLimit", "message": "Expression or call nesting limit exceeded", "line": machine.current.get("line", 1), "col": machine.current.get("col", 1)}
        machine.emit("error", machine.current, **error)
    return {"output": machine.output, "return_value": deepcopy(value), "globals": deepcopy(machine.globals),
            "trace": machine.trace, "error": error, "instructions": machine.instructions}
