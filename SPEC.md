# SONATA 1.0 language specification

SONATA programs compute with signed integers, Booleans, and integer arrays. A
bounded interpreter records execution events that the music renderer can turn
into sound. This document specifies the source language, its AST, and its trace.

## A complete program

```sonata
let total = 0;
for i in 1..6 {
    total = total + i;
}
print(total);
return total;
```

This program prints and returns `15`. Its only remaining global variable is
`total`. The range includes its start and excludes its end, so `1..6` visits
`1`, `2`, `3`, `4`, and `5`.

## Source grammar

Source uses ASCII identifiers, decimal integer literals, whitespace, and `//`
comments that extend to the end of a line. Identifiers match
`[A-Za-z_][A-Za-z_0-9]*` and contain at most 128 characters. Keywords are
`let`, `for`, `in`, `if`, `else`, `while`, `fn`, `return`, `true`, `false`,
`assert`, `break`, `continue`, and `import`.

The grammar below uses `*` for repetition and `?` for an optional element.

```text
program       = statement* EOF
statement     = "let" identifier "=" expression ";"
              | target "=" expression ";"
              | expression ";"
              | "return" expression ";"
              | "assert" "(" expression ")" ";"
              | "break" ";" | "continue" ";"
              | "import" identifier ";"
              | "for" identifier "in" expression ".." expression block
              | "while" "(" expression ")" block
              | "if" "(" expression ")" block ("else" block)?
              | "fn" identifier "(" parameters? ")" block ";"?
block         = "{" statement* "}"
parameters    = identifier ("," identifier)*
arguments     = expression ("," expression)*
target        = identifier | expression "[" expression "]"
expression    = literal | identifier | "(" expression ")"
              | "[" arguments? "]"
              | expression "[" expression "]"
              | identifier "(" arguments? ")"
              | unary_operator expression
              | expression binary_operator expression
literal       = decimal_integer | "true" | "false"
```

Function declarations and imports appear at the top level. Conditions require parentheses;
blocks require braces. Semicolons terminate declarations, assignments,
expression statements, and returns. The optional semicolon after a function
declaration has no semantic effect. A return always has a value. Array writes
must ultimately target a named variable, such as `a[i] = value`.

Operator precedence, from lowest to highest:

| Precedence | Operators | Association |
| --- | --- | --- |
| 1 | `\|\|` | Left |
| 2 | `&&` | Left |
| 3 | `==`, `!=` | Left |
| 4 | `<`, `<=`, `>`, `>=` | Left |
| 5 | `+`, `-` | Left |
| 6 | `*`, `/`, `%` | Left |
| 7 | unary `+`, unary `-`, `!` | Right |
| 8 | call and indexing | Left |

## Values and evaluation

Integers range from `-9223372036854775808` to `9223372036854775807`, inclusive.
Every arithmetic result must fit that range. Unary minus directly applied to
the literal `9223372036854775808` produces the minimum integer. That positive
literal overflows when evaluated by itself. Literals may contain at most 20
decimal digits; longer literals fail during parsing.

Division truncates toward zero using integer arithmetic. Remainder is defined
by `a % b = a - (a / b) * b`. For example, `-7 / 3` is `-2` and `-7 % 3` is
`-1`. A zero divisor fails. Unary `+` and `-` and all arithmetic and ordering
operators require integers.

Booleans are distinct from integers. Conditions and logical operators require
Booleans; `1` cannot act as `true`. `&&` evaluates its right operand only when
the left operand is `true`. `||` evaluates its right operand only when the
left operand is `false`. The `!` operator negates a Boolean.

An array contains only integers. The empty array `[]` is valid. Indexes start
at zero, must be integers, and must be within the current array bounds.
Assignment can replace an element but cannot extend an array. Whole-array
assignment may change its length within the configured limit. Array values
are copied at reads, assignments, function boundaries, output, and trace
snapshots. For example, changing `b[0]` after `let b = a` leaves `a` unchanged.

Equality requires matching types. Integer and Boolean equality compares
values; array equality compares lengths and corresponding elements. An
expression such as `1 == true` fails with a type error.

Operands and function arguments evaluate from left to right. Assignment
evaluates the right-hand value first. An array assignment then evaluates its
index expression, resolves the current named array binding, checks its current
bounds, and updates the element. Thus if the index expression reassigns the
array variable, the element update applies to the newly assigned array. Variable
assignment preserves the variable's original type. A function may return any
supported value; functions have no declared return type.

## Variables, functions, and control flow

`let` introduces a variable in the current lexical scope. Redeclaration in the
same scope fails. An inner block can shadow an outer variable. Assignment
updates the nearest visible declaration. Variables declared in a block or
loop leave scope when that block or loop exits.

Each call gets a fresh parameter/local scope. Functions can read and assign
globals, but they cannot see the local variables of their callers. A parameter
can shadow a global. Function names occupy a separate namespace from variable
names. Functions are registered before execution, which permits forward calls
and mutual recursion. Duplicate function names, duplicate parameter names,
and function declarations with a builtin name fail before execution.

`return` exits the current function, or the program when executed at the top
level. A function that reaches its closing brace returns integer `0`. A
program that reaches its end has a `null` return value in the result object.

The endpoints of a `for` range evaluate once, before iteration. Both endpoints
must be integers. The interpreter advances its internal induction value by
one after each completed iteration. A start greater than or equal to the end
produces zero iterations. The loop variable is scoped to the loop and is
reassigned on each iteration. Assigning to it inside the body does not change
the interpreter's next induction value. Each iteration has a fresh body scope.

`while` reevaluates its Boolean condition before each iteration. `if` executes
one branch in a fresh block scope. A return unwinds nested loops and blocks.

`break` exits the nearest loop in the current function. `continue` skips the
remainder of its current iteration. A `for` loop then advances its internal
induction value; a `while` loop reevaluates its condition. Both statements
unwind scopes created inside the iteration. Executing either statement outside
a loop in the current function raises `ControlFlowError`. A called function
cannot break or continue its caller's loop. Unreachable statements do not
trigger this error. A `break` exits without a final `taken: false` loop check.

`assert(condition);` evaluates its condition once. It requires a Boolean and
records a branch event. A false condition raises `AssertionError` immediately;
a true condition allows execution to continue.

The following builtins are available. Arguments are evaluated once, from left
to right, after their argument count is checked. Arrays returned by builtins
obey the same copy semantics and size limit as other arrays.

| Function | Contract |
| --- | --- |
| `print(value)` | Appends one copied value to program output and returns that value. |
| `len(array)` | Returns the integer length of an integer array. |
| `input(index)` | Returns a copy of the fixture value at a zero-based integer index; an absent or out-of-range index raises `IndexError`. |
| `abs(integer)` | Returns the absolute value; the minimum signed integer raises `Overflow`. |
| `min(a, b)`, `max(a, b)` | Return the lesser or greater of exactly two integers. |
| `clamp(value, lower, upper)` | Returns an integer within the inclusive bounds. Reversed bounds raise `ValueError`. |
| `sum(array)` | Adds elements from left to right, checking overflow after each addition; the empty sum is zero. |
| `range(start, end)` | Returns consecutive integers from `start` through `end - 1`; an empty or reversed range returns `[]`. |
| `repeat(value, count)` | Returns `count` copies of an integer. A negative count raises `ValueError`. |

`sum`, `range`, and `repeat` charge one execution step per array element they
consume or produce, in addition to evaluating the call and its arguments.
Array-producing builtins check the requested length before allocating the
result. For example, `sum([9223372036854775807, 1, -1])` overflows at its second
addition even though its mathematical total fits the integer range.

## Reproducible inputs

`execute(ast, limits=None, inputs=None)` accepts an ordered Python list of
fixture values, commonly loaded from a JSON array. `None` supplies an empty
list. Values must be exact Python integers within the signed 64-bit range,
Booleans, or lists containing only such integers. Strings, floats, null values,
nested arrays, and host subclasses are rejected. The entire fixture is checked
and copied before source execution. Mutating an array returned by `input`
cannot modify the supplied fixture or a later read.

There may be at most 4096 fixture entries. Each array must fit `max_array`.
The aggregate budget is 65536 scalar value slots, counting an array by its
number of elements and a scalar as one slot. Invalid fixtures produce an
`InputError` result before any source statement executes. The fixture is
external data: source-code MIDI preserves its reads through `input(index)`,
but does not embed fixture values. Reproducing an execution requires the same
fixture and limits as well as the same program.

## Local source modules

`import helpers;` names `helpers.son` in the entry program's directory.
`sonata.loader.load_source(path)` resolves the module graph before execution.
`load_program(path)` parses that returned source. There is no module search
path, filename string syntax, package download, or host-language import.
Imported files may contain only function declarations and further imports.
All functions share one namespace; duplicate names and builtin names fail.
Functions in imported modules follow ordinary global-variable semantics.

Dependencies are traversed in written import order. Their function declarations
are placed before the importing file's remaining statements. Each resolved file
is included once, including when several files import it. Import cycles fail.
Every dependency must resolve to the selected entry's resolved directory;
symlinks that lead outside it fail. The graph is limited to 32 unique files,
including the entry, and 200000 total source characters. Reads also have an
800000-byte per-file cap to bound UTF-8 input before decoding. Ordinary parser
and AST limits apply to the final bundle.

Without imports, `load_source` returns the original text. With imports it
returns canonical bundled text, reparsed so every trace location refers to
that text. Interfaces must display the bundle when following these locations;
there is no mapping back to individual module files in version 1.0. Compile
the bundle to MIDI for a self-contained executable score. Passing an unresolved
import directly to `execute` or the reference evaluator produces `ImportError`
before any source statement executes. File-resolution failures raise
`SonataImportError`, a Python `ValueError` subclass; syntax failures retain
`SonataSyntaxError`.

## AST and source APIs

`sonata.language.parse(source)` returns a plain dictionary AST or raises
`SonataSyntaxError`, which exposes `message`, `line`, and `col`. Locations are
one-based. Comments, whitespace, and redundant grouping parentheses are not
stored in the AST.

Every AST node has `kind`, `line`, and `col`. Its additional fields follow the
table below. `expr` means another expression node, and `stmts` means a list of
statement nodes.

| Kind | Fields |
| --- | --- |
| `program` | `body: stmts` |
| `int` | `value: nonnegative decimal literal` |
| `bool` | `value: Boolean` |
| `var` | `name: string` |
| `unary` | `op: string`, `value: expr` |
| `binary` | `op: string`, `left: expr`, `right: expr` |
| `array` | `items: list[expr]` |
| `index` | `value: expr`, `index: expr` |
| `call` | `name: string`, `args: list[expr]` |
| `let` | `name: string`, `value: expr` |
| `assign` | `target: var or index node`, `value: expr` |
| `expr_stmt` | `value: expr` |
| `return` | `value: expr` |
| `assert` | `condition: expr` |
| `break`, `continue` | No additional fields. |
| `import` | `name: string` |
| `for` | `name: string`, `start: expr`, `end: expr`, `body: stmts` |
| `while` | `condition: expr`, `body: stmts` |
| `if` | `condition: expr`, `then: stmts`, `else: stmts` |
| `fn` | `name: string`, `params: list[string]`, `body: stmts` |

Negative numbers use a unary node around a nonnegative integer literal.
Builtins use ordinary call nodes. An omitted `else` branch is an empty
list. `canonical(ast)` recursively copies the tree and removes `line` and
`col`. `format_source(ast)` prints source with the same canonical structure.
The interpreter also accepts canonical trees without locations, using `1:1`
where locations are absent. `validate_ast(ast)` rejects malformed nodes,
unknown fields, invalid identifiers/operators, and misplaced node kinds.

## Execution result and trace

`sonata.runtime.execute(program, limits=None, inputs=None)` returns this dictionary:

```text
{
    output: list of printed values,
    return_value: value or null,
    globals: dictionary of remaining global variables,
    trace: list of event dictionaries,
    error: null or {kind, message, line, col},
    instructions: integer
}
```

A semantic or resource error stops execution. The result retains output and
global changes that already occurred. Each successful run with the same AST,
fixtures, and deterministic limits produces the same result. A wall-clock timeout may
stop at different instructions on different runs.

Every event has these fields:

| Field | Meaning |
| --- | --- |
| `id` | Contiguous event index, starting at zero. |
| `kind` | Event category listed below. |
| `line`, `col` | Source location of the event's node. |
| `depth` | Number of active user-function calls; zero in the main program. |
| `function` | Current function name, or `<main>`. |
| `data` | Event-specific dictionary. |
| `variables` | Deep snapshot of visible variables; inner names shadow outer names. |
| `stack` | Function names from `<main>` to the current function. |

The event categories and their data are:

| Kind | Data |
| --- | --- |
| `statement` | `statement`: AST kind, emitted before executing a statement. |
| `declare` | `name`, `value`; function declarations use `name`, `function: true`. |
| `assign` | `name`, `value`, plus `index` for an array element. Loop-variable updates also emit this event. |
| `read` | `name`, `value` for a variable; `index`, `value` for an indexed read; `input`, `value` for a fixture read. |
| `branch` | `taken` for `if`; logical operators add `operator` and `short_circuit`, with `taken` meaning the right operand will be evaluated. Assertions add `assertion: true`; loop control adds `control: "break"` or `"continue"` and `taken: true`. |
| `loop` | `taken`, `iteration`; range loops also include `name` and the internal induction `value`. |
| `call` | `name`, `arguments`, emitted in the user function after parameters are bound. |
| `return` | `value`; implicit function returns also contain `implicit: true`. |
| `output` | `value`, emitted by `print`. |
| `error` | `kind`, `message`, `line`, `col`; always the final event of a failed execution. |

Normal loop completion records a final check with `taken: false`. A break,
return, or error inside a loop exits immediately, so there is no later terminal check.
Range-loop checks occur before the next loop-variable assignment; their
`data.value` records the upcoming induction value. An error event retains the
variables and call stack where the failure occurred, including locals from
blocks that unwound. Builtins execute in their caller's context; user-function
calls receive separate call events and stack frames.

## Limits and failures

`Limits` is an immutable dataclass. Its defaults and accepted configuration
ranges are:

| Setting | Default | Accepted values |
| --- | --- | --- |
| `max_steps` | `10000` | Integer from 1 through 1000000. |
| `max_depth` | `32` | Integer from 1 through 128. |
| `max_array` | `256` | Integer from 0 through 4096. |
| `timeout_seconds` | `None` | `None`, or a finite nonnegative number. |
| `max_trace_values` | `2000000` | Integer from 1 through 10000000. |

The step budget counts statement entry, expression evaluation, loop
condition checks, and per-element work in `sum`, `range`, and `repeat`.
Function declarations are registered before this count
starts; visiting a declaration during normal execution still counts as a
statement. The instruction count never exceeds `max_steps`.

The trace budget counts visible bindings, copied array elements, event data,
and stack entries using a deterministic accounting rule. It bounds trace
growth independently of the step budget. One final error event is allowed
after that budget is exhausted. The limit is a count of value slots, not an
exact byte count of Python allocations.

Source is limited to 200000 characters. Parsing limits nested expressions and
statements to 64 parser levels. ASTs are limited to 20000 nodes and depth 64.
Combined expression and block execution nesting is capped at 128 in addition
to the configured user-function call-depth limit. These fixed bounds also
apply to ASTs loaded through a decoder. The interpreter evaluates only its
own AST nodes and provides no host-code execution, filesystem, network,
clock, or random-number operation to programs. The host-side module loader
resolves local source imports before interpretation.

Runtime error kinds are `NameError`, `TypeError`, `ArityError`,
`DivisionByZero`, `Overflow`, `IndexError`, `StepLimit`, `DepthLimit`,
`ArrayLimit`, `TraceLimit`, `Timeout`, `InvalidAST`, `AssertionError`,
`ControlFlowError`, `InputError`, `ImportError`, and `ValueError`. Invalid limit
configuration raises Python `ValueError` when constructing `Limits`.

## Compatibility boundary

This version has no strings, floating-point values, nested arrays, closures,
first-class functions, variables declared by imported modules, or concurrent
execution. The AST and trace contracts
above are the interfaces shared by the interpreter, independent evaluator,
and music pipeline. Source locations and trace events describe the program
that was actually executed; canonical AST equality establishes structural
roundtrip preservation, while semantic tests compare computed results.

SC1's note grammar and existing token pitches are unchanged. New reserved words
are spelled through the existing identifier melody. Existing scores remain
readable when they satisfy the 1.0 source grammar. Programs from the prototype
that used `assert`, `break`, `continue`, or `import` as identifiers must rename
those identifiers; functions using newly introduced builtin names must also
be renamed. Version 1.0 does not silently reinterpret these name conflicts.
