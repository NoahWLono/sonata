"""SONATA's source parser and canonical source printer. No host code evaluation."""

from dataclasses import dataclass
import re


class SonataSyntaxError(ValueError):
    def __init__(self, message: str, line: int = 1, col: int = 1):
        self.message, self.line, self.col = message, line, col
        super().__init__(f"{message} at {line}:{col}")


@dataclass(frozen=True)
class Token:
    text: str
    line: int
    col: int


_TOKEN = re.compile(r"//[^\n]*|\s+|[0-9]+|[A-Za-z_][A-Za-z_0-9]*|\.\.|==|!=|<=|>=|&&|\|\||[{}()\[\];,+*/%<>=!\-]")
_RESERVED = {"let", "for", "in", "if", "else", "while", "fn", "return", "true", "false", "assert", "break", "continue", "import"}
_PRECEDENCE = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, "<=": 4, ">": 4, ">=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}


def _node(kind, token, **fields):
    return {"kind": kind, "line": token.line, "col": token.col, **fields}


def _tokens(source):
    if len(source) > 200_000:
        raise SonataSyntaxError("Source exceeds 200000 characters")
    result, pos, line, col = [], 0, 1, 1
    while pos < len(source):
        match = _TOKEN.match(source, pos)
        if not match:
            raise SonataSyntaxError(f"Unexpected character {source[pos]!r}", line, col)
        value = match.group()
        if not value.isspace() and not value.startswith("//"):
            if (value[0].isalpha() or value[0] == "_") and len(value) > 128:
                raise SonataSyntaxError("Identifier exceeds 128 characters", line, col)
            result.append(Token(value, line, col))
        lines = value.split("\n")
        if len(lines) > 1:
            line += len(lines) - 1
            col = len(lines[-1]) + 1
        else:
            col += len(value)
        pos = match.end()
    result.append(Token("<eof>", line, col))
    return result


class _Parser:
    def __init__(self, source):
        self.tokens, self.pos = _tokens(source), 0

    @property
    def token(self):
        return self.tokens[self.pos]

    def take(self, expected=None):
        token = self.token
        if expected is not None and token.text != expected:
            raise SonataSyntaxError(f"Expected {expected!r}, got {token.text!r}", token.line, token.col)
        if token.text == "<eof>":
            raise SonataSyntaxError("Unexpected end of source", token.line, token.col)
        self.pos += 1
        return token

    def identifier(self):
        token = self.take()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token.text) or token.text in _RESERVED:
            raise SonataSyntaxError("Expected identifier", token.line, token.col)
        return token.text

    def block(self, depth):
        self.take("{")
        body = []
        while self.token.text != "}":
            body.append(self.statement(depth + 1))
        self.take("}")
        return body

    def statement(self, depth=0):
        if depth > 64:
            raise SonataSyntaxError("Statement nesting limit exceeded", self.token.line, self.token.col)
        token = self.token
        if token.text in {"break", "continue"}:
            self.take()
            self.take(";")
            return _node(token.text, token)
        if token.text == "assert":
            self.take()
            self.take("(")
            condition = self.expression()
            self.take(")")
            self.take(";")
            return _node("assert", token, condition=condition)
        if token.text == "import":
            if depth:
                raise SonataSyntaxError("Imports must be top-level", token.line, token.col)
            self.take()
            name = self.identifier()
            self.take(";")
            return _node("import", token, name=name)
        if token.text == "let":
            self.take()
            name = self.identifier()
            self.take("=")
            value = self.expression()
            self.take(";")
            return _node("let", token, name=name, value=value)
        if token.text == "for":
            self.take()
            name = self.identifier()
            self.take("in")
            start = self.expression()
            self.take("..")
            end = self.expression()
            return _node("for", token, name=name, start=start, end=end, body=self.block(depth))
        if token.text in {"if", "while"}:
            self.take()
            self.take("(")
            condition = self.expression()
            self.take(")")
            body = self.block(depth)
            if token.text == "while":
                return _node("while", token, condition=condition, body=body)
            otherwise = []
            if self.token.text == "else":
                self.take()
                otherwise = self.block(depth)
            return _node("if", token, condition=condition, then=body, **{"else": otherwise})
        if token.text == "fn":
            if depth:
                raise SonataSyntaxError("Function declarations must be top-level", token.line, token.col)
            self.take()
            name = self.identifier()
            self.take("(")
            params = []
            if self.token.text != ")":
                params.append(self.identifier())
                while self.token.text == ",":
                    self.take()
                    params.append(self.identifier())
            self.take(")")
            body = self.block(depth)
            if self.token.text == ";":
                self.take()
            return _node("fn", token, name=name, params=params, body=body)
        if token.text == "return":
            self.take()
            value = self.expression()
            self.take(";")
            return _node("return", token, value=value)
        value = self.expression()
        if self.token.text == "=":
            self.take()
            if value["kind"] not in {"var", "index"}:
                raise SonataSyntaxError("Assignment requires a variable or array element", token.line, token.col)
            right = self.expression()
            self.take(";")
            return _node("assign", token, target=value, value=right)
        self.take(";")
        return _node("expr_stmt", token, value=value)

    def expression(self, min_precedence=0, depth=0):
        if depth > 64:
            raise SonataSyntaxError("Expression nesting limit exceeded", self.token.line, self.token.col)
        token = self.take()
        if token.text.isdecimal():
            if len(token.text) > 20:
                raise SonataSyntaxError("Integer literal is too large", token.line, token.col)
            value = _node("int", token, value=int(token.text))
        elif token.text in {"true", "false"}:
            value = _node("bool", token, value=token.text == "true")
        elif token.text in {"-", "!", "+"}:
            value = _node("unary", token, op=token.text, value=self.expression(7, depth + 1))
        elif token.text == "[":
            items = []
            if self.token.text != "]":
                items.append(self.expression(depth=depth + 1))
                while self.token.text == ",":
                    self.take()
                    items.append(self.expression(depth=depth + 1))
            self.take("]")
            value = _node("array", token, items=items)
        elif token.text == "(":
            value = self.expression(depth=depth + 1)
            self.take(")")
        elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token.text) and token.text not in _RESERVED:
            value = _node("var", token, name=token.text)
        else:
            raise SonataSyntaxError(f"Expected expression, got {token.text!r}", token.line, token.col)
        while True:
            if self.token.text == "[":
                bracket = self.take()
                index = self.expression(depth=depth + 1)
                self.take("]")
                value = _node("index", bracket, value=value, index=index)
                continue
            if self.token.text == "(" and value["kind"] == "var":
                self.take()
                args = []
                if self.token.text != ")":
                    args.append(self.expression(depth=depth + 1))
                    while self.token.text == ",":
                        self.take()
                        args.append(self.expression(depth=depth + 1))
                self.take(")")
                value = _node("call", token, name=value["name"], args=args)
                continue
            op = self.token.text
            precedence = _PRECEDENCE.get(op, -1)
            if precedence < min_precedence:
                return value
            operator = self.take()
            right = self.expression(precedence + 1, depth + 1)
            value = _node("binary", operator, op=op, left=value, right=right)


def parse(source: str) -> dict:
    """Parse source into plain dictionaries with one-based line/column locations."""
    parser = _Parser(source)
    body = []
    try:
        while parser.token.text != "<eof>":
            body.append(parser.statement())
    except RecursionError:
        raise SonataSyntaxError("Parser nesting limit exceeded", parser.token.line, parser.token.col) from None
    program = {"kind": "program", "line": 1, "col": 1, "body": body}
    validate_ast(program)
    return program


def validate_ast(program: dict) -> None:
    """Validate an AST received from a decoder before interpreting it."""
    expressions = {"int", "bool", "var", "unary", "binary", "array", "index", "call"}
    statements = {"let", "assign", "expr_stmt", "for", "while", "if", "fn", "return", "assert", "break", "continue", "import"}
    shapes = {
        "program": {"body": "statements"}, "int": {"value": "integer"}, "bool": {"value": "boolean"},
        "var": {"name": "name"}, "unary": {"op": "unary_op", "value": "expression"},
        "binary": {"op": "binary_op", "left": "expression", "right": "expression"},
        "array": {"items": "expressions"}, "index": {"value": "expression", "index": "expression"},
        "call": {"name": "name", "args": "expressions"}, "let": {"name": "name", "value": "expression"},
        "assign": {"target": "target", "value": "expression"}, "expr_stmt": {"value": "expression"},
        "return": {"value": "expression"}, "for": {"name": "name", "start": "expression", "end": "expression", "body": "statements"},
        "while": {"condition": "expression", "body": "statements"},
        "if": {"condition": "expression", "then": "statements", "else": "statements"},
        "fn": {"name": "name", "params": "names", "body": "statements"},
        "assert": {"condition": "expression"}, "break": {}, "continue": {}, "import": {"name": "name"},
    }
    pending, count = [(program, 0, "program")], 0
    while pending:
        node, depth, expected = pending.pop()
        count += 1
        line = node.get("line", 1) if type(node) is dict else 1
        col = node.get("col", 1) if type(node) is dict else 1

        def invalid(message):
            raise SonataSyntaxError(message, line if type(line) is int else 1, col if type(col) is int else 1)

        if depth > 64 or count > 20_000:
            invalid("AST complexity limit exceeded")
        if type(node) is not dict or type(node.get("kind")) is not str or node["kind"] not in shapes:
            invalid("Invalid AST node")
        kind = node["kind"]
        if (expected == "program" and kind != "program") or (expected == "statement" and kind not in statements) or (expected == "expression" and kind not in expressions) or (expected == "target" and kind not in {"var", "index"}):
            invalid("AST node occurs in an invalid position")
        if kind == "fn" and depth != 1:
            invalid("Function declarations must be top-level")
        if kind == "import" and depth != 1:
            invalid("Imports must be top-level")
        if type(line) is not int or type(col) is not int or line < 1 or col < 1:
            invalid("Invalid AST source location")
        if set(node) - set(shapes[kind]) - {"kind", "line", "col"}:
            invalid("Unknown AST field")
        for field, field_type in shapes[kind].items():
            if field not in node:
                invalid(f"Missing AST field {field!r}")
            value = node[field]
            if field_type in {"expression", "target"}:
                pending.append((value, depth + 1, field_type))
            elif field_type in {"statements", "expressions", "names"}:
                if type(value) is not list or len(value) > 20_000:
                    invalid("Invalid AST list")
                if field_type == "names":
                    if not all(type(item) is str and len(item) <= 128 and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", item) and item not in _RESERVED for item in value):
                        invalid("Invalid parameter name")
                else:
                    pending.extend((item, depth + 1, "statement" if field_type == "statements" else "expression") for item in value)
            elif field_type == "name":
                if type(value) is not str or len(value) > 128 or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value) or value in _RESERVED:
                    invalid("Invalid identifier")
            elif field_type == "integer":
                if type(value) is not int or value < 0 or value >= 10**20:
                    invalid("Invalid integer literal")
            elif field_type == "boolean" and type(value) is not bool:
                invalid("Invalid Boolean literal")
            elif field_type == "unary_op" and (type(value) is not str or value not in {"+", "-", "!"}):
                invalid("Invalid unary operator")
            elif field_type == "binary_op" and (type(value) is not str or value not in _PRECEDENCE):
                invalid("Invalid binary operator")


def canonical(ast: dict) -> dict:
    """Return a deep structural copy with source locations removed."""
    if isinstance(ast, dict):
        return {key: canonical(value) for key, value in ast.items() if key not in {"line", "col"}}
    if isinstance(ast, list):
        return [canonical(item) for item in ast]
    return ast


def _expr(node, minimum=0):
    kind = node["kind"]
    if kind == "int":
        return str(node["value"])
    if kind == "bool":
        return "true" if node["value"] else "false"
    if kind == "unary":
        text = f"{node['op']}{_expr(node['value'], 7)}"
        return f"({text})" if minimum > 7 else text
    if kind == "array":
        return "[" + ", ".join(_expr(item) for item in node["items"]) + "]"
    if kind == "index":
        base = _expr(node["value"], 8)
        return f"{base}[{_expr(node['index'])}]"
    if kind == "var":
        return node["name"]
    if kind == "call":
        return f"{node['name']}({', '.join(_expr(arg) for arg in node['args'])})"
    if kind == "binary":
        precedence = _PRECEDENCE[node["op"]]
        text = f"{_expr(node['left'], precedence)} {node['op']} {_expr(node['right'], precedence + 1)}"
        return f"({text})" if precedence < minimum else text
    raise ValueError(f"Unknown expression kind: {kind}")


def format_source(ast: dict, *, compact: bool = False) -> str:
    def statements(body, indent=0):
        lines, prefix = [], "" if compact else "    " * indent
        for node in body:
            kind = node["kind"]
            if kind == "let":
                line = f"let {node['name']} = {_expr(node['value'])};"
            elif kind == "assign":
                line = f"{_expr(node['target'])} = {_expr(node['value'])};"
            elif kind == "return":
                line = f"return {_expr(node['value'])};"
            elif kind in {"break", "continue"}:
                line = kind + ";"
            elif kind == "assert":
                line = f"assert({_expr(node['condition'])});"
            elif kind == "import":
                line = f"import {node['name']};"
            elif kind == "expr_stmt":
                line = _expr(node["value"]) + ";"
            elif kind in {"for", "while", "if", "fn"}:
                if kind == "for":
                    header = f"for {node['name']} in {_expr(node['start'])}..{_expr(node['end'])}"
                elif kind == "fn":
                    header = f"fn {node['name']}({', '.join(node['params'])})"
                else:
                    header = f"{kind} ({_expr(node['condition'])})"
                lines.append(prefix + header + " {")
                lines.extend(statements(node["then"] if kind == "if" else node["body"], indent + 1))
                if kind == "if" and node["else"]:
                    lines.append(prefix + "} else {")
                    lines.extend(statements(node["else"], indent + 1))
                lines.append(prefix + "}")
                continue
            else:
                raise ValueError(f"Unknown statement kind: {kind}")
            lines.append(prefix + line)
        return lines
    return "\n".join(statements(ast["body"])) + "\n"
