# Embed execution and sonification

The Python package exposes the same parser, bounded interpreter, note generator,
and exporters used by the command-line tools. These APIs let an application
inspect computation before deciding how to present it.

## Run SONATA and produce sound

```python
from sonata.language import parse
from sonata.runtime import execute, Limits
from sonata.music import sonify
from sonata.audio import render_wav
from sonata.midi import write_midi

program = parse("let total=0; for i in 1..6 { total=total+i; } return total;")
result = execute(program, Limits(max_steps=1000))
assert result["error"] is None
assert result["return_value"] == 15
notes = sonify(result["trace"], profile={"mapping": "semantic"})
write_midi(notes, "sum.mid")
render_wav(notes, "sum.wav")
```

`execute` returns complete trace snapshots. Each event contains its ID, kind,
source line and column, function, stack depth, call stack, data, and visible
variables. Each generated note keeps `event_id` and `line`. Source-code MIDI
compilation is a separate operation; runtime MIDI cannot reconstruct an AST.

## Versioned listening profiles

`sonify(trace, palette="classical", profile=None)` keeps the original v0.1
mapping when `profile` is omitted. Passing an object, including `{}`, chooses
the stable semantic mapping unless `mapping` explicitly selects `legacy`.

```python
from sonata.profiles import validate_profile

profile = validate_profile({
    "version": 1,
    "mapping": "semantic",
    "event_stride": 0.25,
    "event_kinds": ["declare", "assign", "return", "error"],
    "functions": None,
    "variables": None,
    "ranges": {"total": [0, 15]}
})
notes = sonify(result["trace"], profile=profile)
```

The semantic mapping derives its motif from function name, event kind, named
variable, statement kind, and operator. Comments, spacing, and source-line
changes do not alter these motifs. Function calls and returns retain their
name-derived phrases. A finite set of pitches necessarily has collisions;
semantic profiles improve identity stability without making runtime sound a
lossless state encoding. Executable source MIDI has its own reversible codec.

| Field | Meaning |
| --- | --- |
| `version` | Integer `1`; unknown versions are rejected |
| `mapping` | `semantic` or `legacy` |
| `event_stride` | Beat spacing between original trace events, from 1/32 through 4 |
| `event_kinds` | Event kinds to retain, or `null` for all |
| `functions` | Current function names to retain, or `null` for all |
| `variables` | Named reads/writes and changes in watched snapshots, or `null` |
| `ranges` | Variable name, or fallback `"*"`, mapped to `[minimum, maximum]` |

Filters intersect. An empty list selects nothing; omitted/null filters select
all. Filtering preserves the original clock and event IDs, including gaps for
muted events. Profile-generated notes include `trace_index`, the original list
position. The complete trace remains available for the inspector and comparison.
If a short stride gives an array member less than one MIDI tick, sonification
rejects the profile/run combination and asks for a longer stride. This avoids
quantization merging distinct onsets in dense array arpeggios.

Ranges require signed 64-bit integer endpoints with minimum < maximum. Within a
range, values map monotonically across two scale octaves. Values outside the
range clamp at the end and add a chromatic cue: `cue="below_range"` or
`cue="above_range"`. The range applies to `data.value`, using `data.name` when
available and `"*"` otherwise. It does not continuously resound every variable
in a snapshot. Several values can occupy the same pitch when a range has more
values than available notes. Branch decisions and return cadences retain their
own event-specific musical shapes.

A variable filter also keeps an event when the selected variable's snapshot
changes, including array changes and scope entry/exit. An array-index read with
no named variable tag cannot always be attributed to a specific watched array.
Use an event filter for all array-read events when that distinction matters.

## Compare runs

```python
from sonata.comparison import compare_traces

bug = execute(parse("let total=0; for i in 1..5 { total=total+i; } return total;"))
comparison = compare_traces(result["trace"], bug["trace"], window=4)
assert comparison["equal"] is False
print(comparison["first_divergence"])
```

The comparison reports the first different event at the same trace index and a
window around it. Returned entries contain `index`, `left`, `right`, and `equal`.
An event absent from a shorter trace is `null`. The comparison includes exact
kind, depth, function, data, variables, and stack, distinguishing integer `1`
from Boolean `true`. It excludes event IDs and source line/column metadata.
It does not align later reconverging branches or prove program equivalence.

## Observe a trusted Python callable

```python
from sonata.python_trace import trace_callable, validate_trace_bundle

def sum_to(n):
    total = 0
    for i in range(1, n + 1):
        total += i
    return total

bundle = trace_callable(sum_to, 5, max_events=1000, max_depth=16)
assert bundle["return_value"] == 15
bundle = validate_trace_bundle(bundle)
notes = sonify(bundle["trace"], profile={})
render_wav(notes, "python-sum.wav")
```

Run `python examples/integrations/trace_python.py artifacts/python-fibonacci`
for a complete JSON, MIDI, and WAV example.

The adapter observes a synchronous Python function and descendant calls in the
same source file, in the current thread. It requires CPython because distinguishing
exception unwinding from a successful return uses its return opcodes. Generator
and coroutine functions are excluded. It records calls, line visits, local
variable changes, returns, and exceptions. It does not infer Python conditional
branches or loop boundaries, capture `print` output, or instrument native code.
An exception caught by the function still appears as an observed error event,
while the final `error` field is null if the call succeeds.

Supported snapshot values are signed 64-bit integers, Booleans, and bounded
integer lists/tuples; tuples become arrays. A Python `None` return is also
allowed. Other local values appear by name in `omitted_variables`. Their string
representations are not evaluated. Unsupported return values produce a
structured `UnsupportedValue` error. Assignment changes are observed at the
next Python trace event and attributed to the preceding visited line; several
assignments on one line can collapse into one observed final value.

The bundle uses `schema="sonata-python-trace"` and `version=1`. It includes a
source fragment for the entry function, its `source_start_line`, a filename
without directories, the result/error, and the trace. Descendant functions
outside that fragment can produce valid line numbers not shown in the fragment.
The bundle validator rejects malformed event IDs, locations, stacks, values,
and unsupported fields before external traces reach the sound engine.

`max_events`, `max_depth`, `max_array`, and `max_values` bound the adapter's
recording. A limit failure adds one final error event after the ordinary event
budget. The callable remains trusted Python with access to its normal process
privileges and side effects. These limits do not interrupt blocking native
calls, constrain other threads, or sandbox hostile code. Use the SONATA
interpreter for bounded SONATA execution. Never accept uploaded Python source
and evaluate it through this adapter.

An active Python debugger/profiler using `sys.settrace` must be stopped before
calling the adapter; the adapter rejects an existing tracer. Python documents
trace callbacks as thread-specific and lists their call, line, return, and
exception events in [the tracing reference](https://docs.python.org/3/library/sys.html#sys.settrace).

## MIDI and reusable composition

Use `recording_inputs` to turn a captured performance into deterministic SONATA
inputs. This adapter keeps positive-velocity note-on pitch, velocity, and
timestamp arrays; the saved recording retains all supported channel messages.

```python
import json
from pathlib import Path
from sonata.ports import recording_inputs

recording = json.loads(Path("examples/integrations/recording.json").read_text())
inputs = recording_inputs(recording, max_notes=256)
program = parse("let pitches=input(0); return pitches[0];")
first = execute(program, inputs=inputs)
assert first["return_value"] == 60
assert first == execute(program, inputs=inputs)
```

`sonata midi inputs captured.json --output inputs.json` writes the same fixture
representation for `sonata run program.son --inputs inputs.json`.

`export_stems(notes, directory, bpm=120, palette="classical")` groups standard
note dictionaries by `voice`, falling back to channel, and writes linked MIDI
and WAV parts with a manifest. Original timing is retained. Unsafe voice names
are replaced by generated filenames. Up to 64 voice groups are accepted.

The small composition API and optional live port APIs are described in the
[MIDI guide](MIDI_GUIDE.md). Composition helpers do not change SONATA language
semantics. A composition score contains notes; an interpreter trace contains
computational evidence. Applications can keep both representations available
and use event IDs to connect them.
