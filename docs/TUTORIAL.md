# First programs, first performances

This walkthrough takes one small algorithm through source, execution, sound,
and executable MIDI. You will change a loop bound, compare the resulting
performances, then try input fixtures and modules. It requires Python 3.12 or
newer and an audio output for listening. Running and exporting files also work
without an audio device.

## 1. Install from the release or checkout

Create a virtual environment. These activation commands are for Bash or Zsh:

```sh
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with `.venv\Scripts\Activate.ps1` instead.
From an extracted SONATA source release or repository checkout, install:

```sh
python -m pip install .
sonata --version
```

Alternatively, install the downloaded release wheel by its local filename:

```sh
python -m pip install /path/to/sonata_lang-1.0.0-py3-none-any.whl
```

Replace `/path/to/` with its actual directory. These instructions do not depend
on a PyPI publication. The basic installation needs no DAW, MIDI hardware,
soundfont, JavaScript package manager, or proprietary sound library.

Copy the installed lessons to your working directory:

```sh
sonata examples --output lessons
sonata run lessons/sum.son
sonata debug --open
```

The debugger opens the packaged sum example at `http://127.0.0.1:8765`. If a
browser does not open automatically, visit that address. Leave the terminal
running while using the debugger and press Ctrl+C there when finished. If the
port is already occupied, use `sonata debug --port 8766 --open`.

## 2. Read a program and check its answer

The sum example follows this structure:

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

The range `1..6` includes `1` and excludes `6`. Its five additions produce
`15`. The command's JSON result reports `return_value: 15`, `output: [15]`,
and `error: null`. The instruction count includes expression evaluation and
loop checks; it is not the number of source lines.

A top-level `return` ends the program. `print` adds a value to the output
collection. The `expected-return` and `expected-output` comments in this
manual are test annotations and have no effect on the program.

## 3. Hear the execution

In the debugger, press **Play**. Browser audio starts after that user action.
Watch the selected source location, variable snapshots, and call stack follow
the recorded events. Step through a few events, then click a note and inspect
its source location. Use the [debugger guide](../debugger/README.md) for the
current controls and keyboard shortcuts.

The interpreter completes a bounded run before playback begins. Playback
breakpoints pause navigation through that recorded trace; they do not suspend
a live interpreter or allow variables to be changed halfway through a run.
Editing and running source creates a new execution.

Export the same kind of runtime performance from the command line:

```sh
sonata listen lessons/sum.son --wav sum.wav --midi sum.runtime.mid --semantic
```

Open `sum.wav` in an audio player. The WAV contains original synthesized audio;
`sum.runtime.mid` contains musical events for an external synthesizer or DAW.
A different synthesizer may use different timbres. The `--semantic` option
selects motifs based on semantic identifiers rather than source line numbers,
which helps preserve motifs when comments or whitespace change.

You can choose another palette without changing the computed answer:

```sh
sonata listen lessons/sum.son --wav sum.ambient.wav --palette ambient --semantic
```

The available palettes are `classical`, `electronic`, and `ambient`.
Learn the intended cues and their limits in the
[listening guide](LISTENING_GUIDE.md). Being able to hear a difference does not
by itself establish that a listener understands the defect that caused it.

## 4. Encode source as executable music

The following commands create a different MIDI representation:

```sh
sonata compile lessons/sum.son --midi sum.code.mid
sonata decode sum.code.mid --output sum.decoded.son
sonata run sum.decoded.son
```

The decoded program returns `15`. Its formatting may differ because the score
preserves canonical program structure rather than whitespace or comments.
Actual pitches, channels, and rhythmic cells carry that structure, including
an audible checksum. Removing invisible text metadata does not remove the
encoded program.

Keep the two file purposes distinct:

| File | What it represents | What you can do with it |
| --- | --- | --- |
| `sum.code.mid` | The source program's executable SC1 encoding. | Decode it back to SONATA and execute it. |
| `sum.runtime.mid` | Musical events derived from this execution. | Listen, arrange, or inspect them; they do not reconstruct the source. |
| `sum.wav` | A synthesized performance of execution events. | Listen or use it in media; SONATA does not decode WAV into source. |

An arbitrary MIDI song is not an executable SONATA program. Editing an SC1
score freely in a DAW may invalidate its grid, tokens, or checksum. The
debugger's score editor validates token edits and regenerates the score.

Run the verifier and save its report:

```sh
sonata verify lessons/sum.son --report verification.json
```

It compares computed results with an independent evaluator, checks trace and
musical provenance, round-trips the executable score, and checks audio output.
The implementations share some dependencies, including the parser; this is a
cross-check with documented assumptions rather than a formal proof of the
entire toolchain.

## 5. Introduce a real off-by-one bug

Change the upper bound from `6` to `5`:

```sonata
// expected-return: 10
// expected-output: [10]
let total = 0;
for i in 1..5 {
    total = total + i;
}
print(total);
return total;
```

This executes four additions and returns `10`. It is a valid SONATA program,
but it is wrong for the stated task of summing one through five. A compiler
cannot infer that intended task from the loop alone.

The lessons include both versions. Compare them and export both performances:

```sh
sonata compare lessons/sum.son lessons/off_by_one.son --report comparison.json --wav-dir comparison --semantic
```

Open `comparison/left.wav` and `comparison/right.wav`. The JSON report records
where the execution traces first differ and shows the results of both runs.
In the debugger, use its two-run comparison controls to align and inspect the
changed region. The comparison and listening controls are described in the
[debugger guide](../debugger/README.md).

An assertion makes the intended answer explicit:

```sonata
// expected-error: "AssertionError"
let total = 0;
for i in 1..5 {
    total = total + i;
}
assert(total == 15);
return total;
```

The failed assertion stops execution with a source location and an error event
that receives a dissonant musical cue. The debugger preserves the partial
trace for inspection.

## 6. Try the same algorithm on external inputs

Run the packaged fixture example:

```sh
sonata run lessons/fixtures.son --inputs lessons/fixtures.json
sonata listen lessons/fixtures.son --inputs lessons/fixtures.json --wav fixtures.wav --semantic
sonata verify lessons/fixtures.son --inputs lessons/fixtures.json
```

The JSON fixture is `[[5, -2, 8, 3], 0]`. The program reads the values with
`input(0)` and the threshold with `input(1)`, ignores entries below the
threshold, and returns `16`. Change a copy of the JSON to try another case.
The source stays the same.

You can compare two fixtures against one source file using
`--left-inputs` and `--right-inputs`:

```sh
sonata compare lessons/fixtures.son lessons/fixtures.son --left-inputs lessons/fixtures.json --right-inputs lessons/fixtures.json --report same-input.json
```

This intentionally compares identical inputs and should show no behavioral
difference. Replace one fixture filename with your changed case to investigate
its effect. Keep fixtures alongside the source or executable MIDI when sharing
the example; the MIDI file does not embed external inputs.

## 7. Reuse functions through a local module

The module lesson computes the sum of the squares from one through five:

```sh
sonata run lessons/modules/main.son
sonata bundle lessons/modules/main.son --output module.bundle.son
sonata run module.bundle.son
```

Both runs return `55`. Open the three files in `lessons/modules` to follow the
imports. `main.son` imports `statistics.son`, which imports `arithmetic.son`.
The bundle is a self-contained program containing their functions.

Imports are restricted to sibling `.son` files, and imported modules may
contain only functions and further imports. The debugger displays the bundled
source so its line numbers match the execution trace. See the
[language guide](LANGUAGE_GUIDE.md#organize-local-functions-into-modules) for the
module rules and resource limits.

## 8. Choose another experiment

The packaged examples include recursive Fibonacci, factorial, bubble sort,
successful and unsuccessful binary search, and bounded runaway recursion.
Try one with the debugger:

```sh
sonata debug lessons/fibonacci.son --open
```

Calls and returns produce recurring structures; array updates produce changing
note sequences. The runaway-recursion example terminates with a configured
limit error. Such a result identifies a bound reached during that run.
Establishing nontermination requires additional reasoning.

For the next steps, use the [language guide](LANGUAGE_GUIDE.md) as a working
reference, the [MIDI guide](MIDI_GUIDE.md) to route sound into instruments and
DAWs, and the [embedding guide](EMBEDDING.md) to call SONATA from Python. The
research materials describe how to investigate human debugging performance
without confusing a measurable signal difference with a demonstrated benefit.
