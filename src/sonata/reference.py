"""Small independent interpreter used as a semantic cross-check.

Only syntax parsing and its exception class are shared with the main implementation. This module
does not consume execution traces or import the runtime, music mapping, or score
codec. It checks successful programs within its own conservative fuel budget;
resource accounting and diagnostic wording are deliberately independent.

The supported successful subset is the bundled executable language: signed
64-bit integers, strict booleans, integer arrays, lexical blocks, conditionals,
bounded loops, first-order recursive functions, assertions, bounded builtins,
and recorded input fixtures. Filesystem modules must be bundled beforehand.
Limits are 100,000 AST visits,
64 nested function calls, and 4,096 array elements by default. There is no trace,
clock deadline, or musical state. Arrays are represented by immutable tuples
internally, making copy-on-assignment and copy-on-call semantics independent of
the main runtime's storage strategy.
"""

from .language import SonataSyntaxError, parse


_MIN_INT = -(1 << 63)
_MAX_INT = (1 << 63) - 1


def _public(value):
    return list(value) if type(value) is tuple else value


class _ReferenceFailure(Exception):
    def __init__(self, code, message, node=None):
        super().__init__(message)
        self.code = code
        self.node = node or {}


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _LoopSignal(Exception):
    def __init__(self, continue_loop):
        self.continue_loop = continue_loop


class _Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.values = {}

    def binding(self, name, node):
        if name in self.values:
            return self
        if self.parent is not None:
            return self.parent.binding(name, node)
        raise _ReferenceFailure("NameError", f"Undefined variable {name}", node)


class _Evaluator:
    def __init__(self, fuel, max_depth, max_array):
        self.fuel = fuel
        self.max_depth = max_depth
        self.max_array = max_array
        self.depth = 0
        self.global_env = _Environment()
        self.output = []
        self.functions = {}
        self.loop_level = 0
        self.inputs = ()

    def fixtures(self, inputs):
        if inputs is None:
            return
        if type(inputs) is not list or len(inputs) > 4096:
            raise _ReferenceFailure("InputError", "Invalid input fixture container")
        copied, cost = [], 0
        for item in inputs:
            if type(item) is list:
                if len(item) > self.max_array:
                    raise _ReferenceFailure("InputError", "Input array exceeds limit")
                for element in item:
                    if type(element) is not int or element < _MIN_INT or element > _MAX_INT:
                        raise _ReferenceFailure("InputError", "Invalid input array element")
                copied.append(tuple(item))
                cost += len(item)
            elif type(item) is bool or (type(item) is int and _MIN_INT <= item <= _MAX_INT):
                copied.append(item)
                cost += 1
            else:
                raise _ReferenceFailure("InputError", "Unsupported input value")
            if cost > 65536:
                raise _ReferenceFailure("InputError", "Input value budget exhausted")
        self.inputs = tuple(copied)

    def tick(self, node):
        self.fuel -= 1
        if self.fuel < 0:
            raise _ReferenceFailure("StepLimit", "Reference fuel exhausted", node)

    @staticmethod
    def integer(value, node):
        if type(value) is not int:
            raise _ReferenceFailure("TypeError", "Expected integer", node)
        if not _MIN_INT <= value <= _MAX_INT:
            raise _ReferenceFailure("Overflow", "Integer is outside signed 64-bit range", node)
        return value

    @staticmethod
    def boolean(value, node):
        if type(value) is not bool:
            raise _ReferenceFailure("TypeError", "Expected boolean", node)
        return value

    @staticmethod
    def array(value, node):
        if type(value) is not tuple:
            raise _ReferenceFailure("TypeError", "Expected integer array", node)
        return value

    def position(self, value, index, node):
        values = self.array(value, node)
        position = self.integer(index, node)
        if position < 0 or position >= len(values):
            raise _ReferenceFailure("IndexError", "Array index is outside its bounds", node)
        return position

    def prepare(self, body):
        for node in body:
            if node["kind"] == "import":
                raise _ReferenceFailure("ImportError", "Reference evaluator requires bundled source", node)
            if node["kind"] != "fn":
                continue
            name = node["name"]
            if name in self.functions or name in {"print", "len", "input", "abs", "min", "max", "clamp", "sum", "range", "repeat"}:
                raise _ReferenceFailure("NameError", f"Duplicate function {name}", node)
            if len(set(node["params"])) != len(node["params"]):
                raise _ReferenceFailure("NameError", "Duplicate function parameter", node)
            self.functions[name] = node

    def call(self, node, env):
        name = node["name"]
        arities = {"print": 1, "len": 1, "input": 1, "abs": 1, "min": 2, "max": 2,
                   "clamp": 3, "sum": 1, "range": 2, "repeat": 2}
        if name in arities:
            if len(node["args"]) != arities[name]:
                raise _ReferenceFailure("ArityError", f"Incorrect argument count for {name}", node)
            args = [self.expression(arg, env) for arg in node["args"]]
            if name == "print":
                self.output.append(_public(args[0]))
                return args[0]
            if name == "len":
                return len(self.array(args[0], node))
            if name == "input":
                index = self.integer(args[0], node)
                if index < 0 or index >= len(self.inputs):
                    raise _ReferenceFailure("IndexError", "Input index is outside fixture bounds", node)
                return self.inputs[index]
            if name == "sum":
                total = 0
                for item in self.array(args[0], node):
                    self.tick(node)
                    total = self.integer(total + item, node)
                return total
            integers = [self.integer(arg, node) for arg in args]
            if name == "abs":
                return self.integer(-integers[0] if integers[0] < 0 else integers[0], node)
            if name == "min":
                return integers[0] if integers[0] <= integers[1] else integers[1]
            if name == "max":
                return integers[0] if integers[0] >= integers[1] else integers[1]
            if name == "clamp":
                value, lower, upper = integers
                if lower > upper:
                    raise _ReferenceFailure("ValueError", "Invalid clamp interval", node)
                return lower if value < lower else upper if value > upper else value
            start, end = integers
            size = max(0, end - start) if name == "range" else end
            if size < 0:
                raise _ReferenceFailure("ValueError", "Invalid repetition count", node)
            if size > self.max_array:
                raise _ReferenceFailure("ArrayLimit", "Array result exceeds configured bound", node)
            items = []
            for offset in range(size):
                self.tick(node)
                items.append(start + offset if name == "range" else start)
            return tuple(items)
        if name not in self.functions:
            raise _ReferenceFailure("NameError", f"Undefined function {name}", node)
        function = self.functions[name]
        if len(node["args"]) != len(function["params"]):
            raise _ReferenceFailure("ArityError", f"Wrong number of arguments for {name}", node)
        if self.depth >= self.max_depth:
            raise _ReferenceFailure("DepthLimit", "Reference function depth exhausted", node)
        args = [self.expression(arg, env) for arg in node["args"]]
        local = _Environment(self.global_env)
        local.values.update(zip(function["params"], args))
        self.depth += 1
        outer_loop = self.loop_level
        self.loop_level = 0
        try:
            self.statements(function["body"], local)
        except _Return as returned:
            return returned.value
        finally:
            self.depth -= 1
            self.loop_level = outer_loop
        return 0

    def binary(self, node, env):
        op = node["op"]
        left = self.expression(node["left"], env)
        if op in {"&&", "||"}:
            left = self.boolean(left, node)
            if (op == "&&" and not left) or (op == "||" and left):
                return left
            return self.boolean(self.expression(node["right"], env), node)
        right = self.expression(node["right"], env)
        if op in {"==", "!="}:
            if type(left) is not type(right):
                raise _ReferenceFailure("TypeError", "Equality operands must have the same type", node)
            return (left == right) if op == "==" else (left != right)
        left = self.integer(left, node)
        right = self.integer(right, node)
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "+":
            result = left + right
        elif op == "-":
            result = left - right
        elif op == "*":
            result = left * right
        elif op in {"/", "%"}:
            if right == 0:
                raise _ReferenceFailure("DivisionByZero", "Zero divisor", node)
            quotient = abs(left) // abs(right)
            if (left < 0) != (right < 0):
                quotient = -quotient
            result = quotient if op == "/" else left - quotient * right
        else:
            raise _ReferenceFailure("TypeError", f"Unknown binary operator {op}", node)
        return self.integer(result, node)

    def expression(self, node, env):
        self.tick(node)
        kind = node["kind"]
        if kind == "int":
            return self.integer(node["value"], node)
        if kind == "bool":
            return node["value"]
        if kind == "var":
            return env.binding(node["name"], node).values[node["name"]]
        if kind == "binary":
            return self.binary(node, env)
        if kind == "unary":
            operand = node["value"]
            if node["op"] == "-" and operand["kind"] == "int" and operand["value"] == 1 << 63:
                return _MIN_INT
            value = self.expression(operand, env)
            if node["op"] == "!":
                return not self.boolean(value, node)
            if node["op"] == "+":
                return self.integer(value, node)
            if node["op"] == "-":
                return self.integer(-self.integer(value, node), node)
            raise _ReferenceFailure("TypeError", "Unknown unary operator", node)
        if kind == "array":
            if len(node["items"]) > self.max_array:
                raise _ReferenceFailure("ArrayLimit", "Reference array length exhausted", node)
            return tuple(self.integer(self.expression(item, env), item) for item in node["items"])
        if kind == "index":
            array = self.expression(node["value"], env)
            index = self.expression(node["index"], env)
            return array[self.position(array, index, node)]
        if kind == "call":
            return self.call(node, env)
        raise _ReferenceFailure("TypeError", f"Unsupported expression {kind}", node)

    def assignment(self, node, env):
        value = self.expression(node["value"], env)
        target = node["target"]
        if target["kind"] == "var":
            name = target["name"]
            owner = env.binding(name, target)
            if type(value) is not type(owner.values[name]):
                raise _ReferenceFailure("TypeError", "Assignment changes variable type", node)
            owner.values[name] = value
            return
        if target["kind"] == "index" and target["value"]["kind"] == "var":
            name = target["value"]["name"]
            index = self.expression(target["index"], env)
            owner = env.binding(name, target)
            array = owner.values[name]
            position = self.position(array, index, target)
            value = self.integer(value, node)
            owner.values[name] = array[:position] + (value,) + array[position + 1:]
            return
        raise _ReferenceFailure("TypeError", "Array assignment requires a variable", target)

    def statements(self, body, env):
        for node in body:
            self.tick(node)
            kind = node["kind"]
            if kind == "assert":
                if not self.boolean(self.expression(node["condition"], env), node):
                    raise _ReferenceFailure("AssertionError", "Assertion failed", node)
            elif kind in {"break", "continue"}:
                if self.loop_level == 0:
                    raise _ReferenceFailure("ControlFlowError", "Loop control outside a function-local loop", node)
                raise _LoopSignal(kind == "continue")
            elif kind == "let":
                if node["name"] in env.values:
                    raise _ReferenceFailure("NameError", f"Duplicate variable {node['name']}", node)
                env.values[node["name"]] = self.expression(node["value"], env)
            elif kind == "assign":
                self.assignment(node, env)
            elif kind == "expr_stmt":
                self.expression(node["value"], env)
            elif kind == "return":
                raise _Return(self.expression(node["value"], env))
            elif kind == "for":
                start = self.integer(self.expression(node["start"], env), node)
                end = self.integer(self.expression(node["end"], env), node)
                for value in range(start, end):
                    self.tick(node)
                    local = _Environment(env)
                    local.values[node["name"]] = value
                    if not self.iteration(node["body"], _Environment(local)):
                        break
            elif kind == "while":
                while True:
                    self.tick(node)
                    if not self.boolean(self.expression(node["condition"], env), node):
                        break
                    if not self.iteration(node["body"], _Environment(env)):
                        break
            elif kind == "if":
                test = self.boolean(self.expression(node["condition"], env), node)
                self.statements(node["then"] if test else node["else"], _Environment(env))
            elif kind == "fn":
                if env is not self.global_env:
                    raise _ReferenceFailure("TypeError", "Function must be declared at top level", node)
            else:
                raise _ReferenceFailure("TypeError", f"Unsupported statement {kind}", node)

    def iteration(self, body, env):
        self.loop_level += 1
        try:
            self.statements(body, env)
        except _LoopSignal as signal:
            return signal.continue_loop
        finally:
            self.loop_level -= 1
        return True


def evaluate(source: str, *, fuel: int = 100_000, max_depth: int = 64, max_array: int = 4096, inputs=None) -> dict:
    """Evaluate source with independent semantics and a shared syntax parser.

    The four observable fields match the main runtime. Reference resource
    limits are not equivalent to traced-runtime limits, so compare successful
    outcomes only when both runs complete within their respective budgets.
    """
    for name, limit in (("fuel", fuel), ("max_depth", max_depth), ("max_array", max_array)):
        if type(limit) is not int or limit < (0 if name == "max_array" else 1):
            raise ValueError(f"{name} must be a valid nonnegative limit")
    runner = _Evaluator(fuel, max_depth, max_array)
    value = None
    error = None
    try:
        program = parse(source)
        runner.fixtures(inputs)
        runner.prepare(program["body"])
        runner.statements(program["body"], runner.global_env)
    except _Return as returned:
        value = returned.value
    except _ReferenceFailure as failure:
        error = {
            "kind": failure.code,
            "message": str(failure),
            "line": failure.node.get("line", 1),
            "col": failure.node.get("col", 1),
        }
    except SonataSyntaxError as failure:
        error = {"kind": "SyntaxError", "message": str(failure), "line": failure.line, "col": failure.col}
    except RecursionError:
        error = {"kind": "DepthLimit", "message": "Reference host stack exhausted", "line": 1, "col": 1}
    return {
        "return_value": _public(value),
        "output": runner.output,
        "globals": {name: _public(value) for name, value in runner.global_env.values.items()},
        "error": error,
    }


evaluate_reference = evaluate
