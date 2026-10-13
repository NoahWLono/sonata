# The SONATA language guide

SONATA lets you write small algorithms, run them under explicit limits, and
inspect their behavior through a trace and a musical performance. You can also
encode the source itself as an executable MIDI score. These are two different
uses of music: one describes the program's structure; the other describes a
particular execution.

Start with the [hands-on tutorial](TUTORIAL.md) if you want to hear a program
before learning all the language rules. This guide explains the language with
complete examples. Comments beginning `expected-return`, `expected-output`, or
`expected-error` describe test expectations; they have no effect on SONATA.
The repository tests execute these examples and compare successful results
with the independent evaluator.

## Write a program

Save this as `total.son`:

```sonata
// expected-return: 15
// expected-output: [15]
let total = 0;
for i in 1..6 {
    total = total + i;
}
print(total);
return total;
```

Run `sonata run total.son`. The command prints a JSON result with
`return_value: 15`, `output: [15]`, the remaining global variables, and
`error: null`. `print` adds a value to the program's output collection; the
command presents that collection inside its JSON result.

A program is a sequence of statements. Use semicolons after variable
declarations, assignments, calls, assertions, returns, `break`, `continue`,
and imports. Use braces around the bodies of functions, loops, and branches.
Comments start with `//` and continue to the end of the line. Identifiers use
ASCII letters, digits, and underscores and cannot start with a digit.

## Values and variables

There are three value types:

| Type | Examples | Restrictions |
| --- | --- | --- |
| Integer | `0`, `42`, `-7` | Signed 64-bit range. |
| Boolean | `true`, `false` | Separate from integers. |
| Integer array | `[]`, `[8, 3, -2]` | One dimension; bounded length. |

`let` declares a variable in the current scope. Assignment changes its value
but must preserve its type. An array can be replaced with an array of a
different length within the configured limit.

```sonata
// expected-return: 12
let count = 4;
count = count * 3;
let ready = true;
if (ready) {
    let count = 99;
    assert(count == 99);
}
return count;
```

The inner declaration shadows the outer `count` until the block ends. An
assignment without a new `let` updates the nearest visible declaration.
Declaring the same name twice in one scope raises `NameError`.

SONATA has no strings, floating-point numbers, nested arrays, objects, or
implicit conversions. `let count = 4; count = true;` raises `TypeError`.
Booleans do not convert to integers.

## Arithmetic and comparisons

Arithmetic operators are `+`, `-`, `*`, `/`, and `%`. Division truncates toward
zero; the remainder has the sign of the dividend when nonzero. The following
is a complete program:

```sonata
// expected-return: [-2, -1, 2, 1]
return [-7 / 3, -7 % 3, 7 / 3, 7 % 3];
```

Integers range from `-9223372036854775808` through `9223372036854775807`.
Every arithmetic result must fit that range. Overflow raises an error; values
do not wrap. Division or remainder by zero raises `DivisionByZero`.

Comparisons `<`, `<=`, `>`, and `>=` require integers. Equality `==` and
inequality `!=` require operands of the same type. Array equality compares
lengths and elements. Logical operators `&&`, `||`, and `!` require Booleans.
The right side of `&&` or `||` runs only when needed:

```sonata
// expected-return: true
let denominator = 0;
return denominator == 0 || 10 / denominator > 1;
```

The division is skipped, so this program succeeds. Multiplication, division,
and remainder bind more tightly than addition and subtraction. Comparisons
bind more tightly than `&&`, which binds more tightly than `||`. Parentheses
make intent explicit. The complete precedence table is in [SPEC.md](../SPEC.md).

## Choose a branch

Conditions require a Boolean enclosed in parentheses. An `else` block is
optional. Use a nested `if` inside `else` for more than two cases.

```sonata
// expected-return: 7
let value = -7;
if (value < 0) {
    return -value;
} else {
    return value;
}
```

The execution trace records which branch ran. A false condition selects the
`else` block, or continues after the statement when there is no `else`.
Musical branches express that choice. Assertions and tests can check whether
it matches the intended algorithm.

## Repeat work

A `for` range includes its start and excludes its end. Its endpoints are
evaluated once, before the loop. The induction variable belongs to the loop,
and each iteration gets a fresh body scope.

```sonata
// expected-return: 6
let total = 0;
for i in 1..4 {
    total = total + i;
}
return total;
```

This visits `1`, `2`, and `3`. A start at or above the end produces no
iterations. Assigning to the loop variable inside its body does not change
the internal induction sequence. To choose each subsequent value yourself,
use `while`:

```sonata
// expected-return: 16
let value = 1;
while (value < 10) {
    value = value * 2;
}
return value;
```

`break` exits the nearest loop. `continue` skips the rest of the current
iteration, then advances a `for` loop or checks a `while` condition again.

```sonata
// expected-return: 7
let values = [2, -1, 5, 99, 8];
let total = 0;
for i in 0..len(values) {
    if (values[i] == 99) {
        break;
    }
    if (values[i] < 0) {
        continue;
    }
    total = total + values[i];
}
return total;
```

Loop control applies within the current function. A function called by a loop
cannot break or continue that caller's loop. Executing either statement outside
a loop in the current function raises `ControlFlowError`.

## Define functions and recurse

Declare functions at the top level with `fn`. Functions can be called before
their declaration and can call themselves or each other.

```sonata
// expected-return: 120
fn factorial(n) {
    assert(n >= 0);
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
return factorial(5);
```

Arguments evaluate from left to right. Each call receives its own parameter
and local-variable scope. Functions can read and change globals, but cannot
see their callers' local variables. There are no closures or function values.
A parameter may shadow a global variable. Function names use a separate
namespace from variables, and builtin function names cannot be redefined.

`return` unwinds the current function's loops and blocks and exits it. At the
top level, it exits the program. A function without an explicit return produces
integer `0`; a program that ends without returning has JSON `null` as its
result. A function may return any supported value type.

Recursion has a configured depth limit as well as an instruction limit. The
trace preserves the exact call depth even though the music uses a finite
number of voices and registers.

## Work with arrays

Array indexes start at zero. Reads and writes require an integer index within
the current bounds; negative indexes are errors. Element assignment cannot
extend an array. Array elements must be integers.

Arrays have value semantics: reads, assignments, calls, returns, and output
copy their contents. Changing a copy does not change the original.

```sonata
// expected-return: [9, 2]
// expected-output: [[1, 2], [1, 8]]
fn replace_second(values) {
    values[1] = 8;
    return values;
}
let original = [1, 2];
let copy = original;
copy[0] = 9;
let changed = replace_second(original);
print(original);
print(changed);
return copy;
```

For `array[index] = value`, the right-hand value evaluates first, then the
index expression, then the current array binding is located and updated.
This matters if those expressions call functions that modify a global array.
Array writes must target a named array, such as `values[i]`.

## Use the small standard library

| Function | Result |
| --- | --- |
| `print(value)` | Appends a copied value to output and returns that value. |
| `len(array)` | Array length. |
| `input(index)` | A copy of an externally supplied fixture value. |
| `abs(value)` | Integer absolute value. |
| `min(a, b)`, `max(a, b)` | Lesser or greater of two integers. |
| `clamp(value, lower, upper)` | Value restricted to inclusive integer bounds. |
| `sum(array)` | Left-to-right sum, checking overflow at each addition. |
| `range(start, end)` | Array containing consecutive integers, excluding `end`. |
| `repeat(value, count)` | Array containing `count` copies of an integer. |

```sonata
// expected-return: 21
let values = range(-2, 4);
let baseline = repeat(3, len(values));
let total = sum(values) + sum(baseline);
assert(clamp(total, 0, 10) == 10);
assert(abs(min(-9, max(1, 5))) == 9);
return total;
```

`range(4, 2)` and `repeat(7, 0)` return empty arrays. A negative repetition
count or reversed clamp bounds raises `ValueError`. Taking the absolute value
of the minimum signed integer overflows. Array-producing builtins check the
length before allocation. `sum`, `range`, and `repeat` charge an execution
step for each element they consume or produce.

## Supply reproducible input fixtures

Fixtures let you try different inputs without changing source. Save an ordered
JSON array such as `[[5, -2, 8, 3], 0]` in `case.json`. The first entry is an
integer array and the second is the threshold.

```sonata
// inputs: [[5, -2, 8, 3], 0]
// expected-return: 16
let values = input(0);
let threshold = input(1);
let total = 0;
for i in 0..len(values) {
    if (values[i] < threshold) {
        continue;
    }
    total = total + values[i];
}
return total;
```

Save the program as `measurements.son`, then run:

```sh
sonata run measurements.son --inputs case.json
sonata listen measurements.son --inputs case.json --wav measurements.wav
sonata verify measurements.son --inputs case.json
```

The whole fixture is validated and copied before execution. Supported entries
are integers, Booleans, and integer arrays. Each array must fit the configured
array limit. There may be at most 4096 entries and 65536 scalar value slots
across the fixture. Unsupported or oversized values produce `InputError`.
Without `--inputs`, the fixture is empty. An absent index raises `IndexError`.

The fixture is a separate artifact. Executable MIDI encodes the call to
`input(0)` but does not embed the value stored at index zero. Keep the source
or score, fixture, execution limits, and listening profile together when
sharing a reproducible experiment.

## Organize local functions into modules

`import statistics;` loads a sibling file named `statistics.son`. Imported
files may contain functions and further imports. They cannot declare global
variables or execute top-level expressions. All loaded functions share one
namespace, so function names must be unique across the graph.

After `sonata examples --output lessons`, inspect
`lessons/modules/arithmetic.son`, `statistics.son`, and `main.son`. The entry is:

```sonata
// fixture-directory: "examples/modules"
// expected-return: 55
import statistics;
let result = sum_squares(range(1, 6));
assert(result == 55);
print(result);
return result;
```

Run or bundle it:

```sh
sonata run lessons/modules/main.son
sonata bundle lessons/modules/main.son --output module.bundle.son
sonata compile lessons/modules/main.son --midi module.code.mid
sonata debug lessons/modules/main.son --open
```

The bundle includes each dependency once, in deterministic import order.
Imports are resolved before execution and are removed from the bundle.
Source locations in traces refer to that bundle, which the debugger displays.
There is no per-module source map in version 1.0.

Modules must remain in the selected entry's resolved directory. The loader
rejects cycles, outside-directory symlinks, duplicate function names, and
imported top-level side effects. It accepts at most 32 files and 200000 total
source characters. SONATA has no package search path or host-language imports.

## Check assumptions and understand errors

An assertion states a property that must be true at that point in execution.
Its condition must be Boolean. Failure stops the program and preserves the
state and output already produced.

```sonata
// expected-error: "AssertionError"
// expected-output: [10]
let total = 10;
print(total);
assert(total == 15);
print(99);
```

`99` is never printed. `sonata run` exits with status 1 on a runtime error and
prints the structured result with the error kind, message, line, and column.
`sonata listen` can render the partial execution through its error event and
also exits with status 1. Syntax and file-loading failures are reported on
standard error before a runtime trace is available.

| Error | Common cause |
| --- | --- |
| `NameError` | Undeclared variable, duplicate declaration, unknown function, or reserved builtin name. |
| `TypeError` | Mixed types or a non-Boolean condition. |
| `ArityError` | Wrong number of function arguments. |
| `IndexError` | Array or fixture index outside its bounds. |
| `Overflow`, `DivisionByZero` | Invalid integer arithmetic. |
| `AssertionError` | A checked condition is false. |
| `ControlFlowError` | A `break` or `continue` has no loop in the current function. |
| `InputError`, `ImportError` | Invalid fixtures or unresolved source imports. |
| `ValueError` | Reversed clamp bounds or a negative repetition count. |
| `StepLimit`, `DepthLimit`, `ArrayLimit`, `TraceLimit`, `Timeout` | A configured or structural execution bound was reached. |

A limit error does not prove that a program is mathematically nonterminating.
It proves that this run exceeded its allowed resources. Increase a bound only
when the program and the intended workload justify doing so.

## Set execution limits

The command line exposes the most common limits:

```sh
sonata run lessons/fibonacci.son --max-steps 20000 --max-depth 40 --max-array 512 --timeout 5
```

The runtime defaults are 10000 instructions, 32 user-function calls of depth,
and 256 elements per array. The CLI applies a three-second timeout by default.
The Python API defaults to no wall-clock timeout. Timeouts can interrupt runs
at different instructions on different machines; deterministic instruction
and size limits make reproducible comparisons easier.

The runtime also bounds trace snapshots, combined expression/block nesting,
and AST size. Audio and MIDI have separate export bounds. Consult
[SPEC.md](../SPEC.md) for the exact accounting and accepted ranges, and the
[embedding guide](EMBEDDING.md) for configuring the Python API.

## Take the next step

Use the [listening guide](LISTENING_GUIDE.md) to learn the auditory vocabulary,
the [debugger guide](../debugger/README.md) for playback and inspection, and the
[MIDI guide](MIDI_GUIDE.md) for ports, external instruments, and DAW workflows.
The [encoding design](ENCODING.md) explains which musical representation is
reversible and which is deliberately lossy. Musical differences are measurable;
whether they improve human debugging remains a research question.
