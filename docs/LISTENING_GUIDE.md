# Learn what SONATA sounds mean

Start with a short program whose answer you know. Listen once while watching
its source and variables, then listen again without following every event.
The aim is to learn recurring cues and notice where a performance changes.
The recorded lessons below make those cues easy to isolate.

These recordings come from actual SONATA executions. They contain original
synthesized sounds and ship with their source, fixtures, trace, notes, profile,
and validation results. No participant data or claims of human debugging
improvement are included.

## Two different things you can hear

**Execution music** follows events that ran: a read, assignment, branch,
function call, return, or error. One program can have different performances
for different inputs. The debugger's **Execution** view links each note to
its event and source location.

**Executable source music** encodes a program's tokens in a precise note
grammar. It includes branches whether or not a particular run takes them.
The debugger's **Executable score** view shows this representation, which can
be decoded from SC1 MIDI back into a canonical program. Arbitrary MIDI music
and rendered WAV are outside that decoder's supported input format.

The listening exercises focus on execution music. The final exercise edits
an executable source score and then hears the changed execution.

## Play the lesson recordings

The full [lesson manifest](../audio/v1/manifest.json) records exact results,
selected event IDs, durations, and measured audio energy. Open the WAV links
in an audio player. Some clips begin with silence because muted source events
retain their original place on the execution clock.

| Lesson | Recordings | Listen for |
| --- | --- | --- |
| Branch decision | [True](../audio/v1/branch_true/execution.wav), [false](../audio/v1/branch_false/execution.wav) | Two different two-note harmonies. |
| Function structure | [Call and return](../audio/v1/call_return/execution.wav) | An entry fifth, followed by fuller return chords. |
| Array ordering | [Three array states](../audio/v1/array_changes/execution.wav) | Notes follow array index order; the final state rises in pitch. |
| Assertion | [Pass](../audio/v1/assertion_pass/execution.wav), [failure](../audio/v1/assertion_error/execution.wav) | The failed branch is followed by a dissonant error cluster. |
| Numerical range | [Inside](../audio/v1/range_inside/execution.wav), [above](../audio/v1/range_above/execution.wav), [below](../audio/v1/range_below/execution.wav) | Outside values add a neighboring chromatic warning tone. |
| Selective listening | [All events](../audio/v1/watch_all/execution.wav), [watch total](../audio/v1/watch_total/execution.wav) | The watched variable's changes remain at their original times. |
| Formatting, semantic mapping | [Compact source](../audio/v1/semantic_original/execution.wav), [formatted source](../audio/v1/semantic_formatted/execution.wav) | The audio is byte-identical in the reproducible build. |
| Formatting, legacy mapping | [Compact source](../audio/v1/legacy_original/execution.wav), [formatted source](../audio/v1/legacy_formatted/execution.wav) | Moving statements between source lines changes the performance. |
| Off-by-one defect | [Sum 15](../audio/v1/score_original/execution.wav), [sum 10](../audio/v1/off_by_one/execution.wav) | The defective loop loses an iteration. |
| Executable score edit | [Before: 15](../audio/v1/score_original/execution.wav), [after: 21](../audio/v1/score_edited/execution.wav) | The edited loop gains the addition of six. |
| Bundled modules | [Sum of squares: 55](../audio/v1/module_bundle/execution.wav) | Repeated imported function calls contribute to one execution. |

The array lesson prints `[5, 1, 4]`, then `[1, 5, 4]`, then `[1, 4, 5]`.
Its listening profile provides a fixed numerical range so the last state's
increasing values produce increasing pitches. It demonstrates array-state
sonification; the full bubble-sort example demonstrates an algorithm that
performs the sorting itself.

Each clip directory contains `source.son`, `inputs.json`, `profile.json`,
`trace.json`, `notes.json`, `execution.wav`, `execution.mid`, `code.mid`,
`decoded.son`, and `validation.json`. The trace file contains the complete
execution result, including its `trace` array. The module lesson also has
an [independent verification report](../audio/v1/module_bundle/independent-verification.json).

From the repository root, reproduce one clip with its exact settings:

```sh
sonata listen audio/v1/range_above/source.son --inputs audio/v1/range_above/inputs.json --profile audio/v1/range_above/profile.json --wav range-above.wav --midi range-above.mid
```

Rebuild every lesson with:

```sh
python scripts/v1_demos.py
```

## Learn the event vocabulary

Musical intervals here are measured in semitones above the event's root pitch.
The palette, current call depth, and semantic identity help select that root.
An interval describes the relative notes, independent of the chosen register.

| Event | Musical rule | What the rule tells you |
| --- | --- | --- |
| Statement | A short note at its mapped pitch. | A statement is being entered. |
| Declaration, assignment, read | A motif influenced by the name and value. | A named value is introduced, changed, or inspected. |
| True branch | Root and root + 5, a perfect fourth. | The recorded decision is true, or a logical right operand will run. |
| False branch | Root and root + 3, a minor third. | The recorded decision is false, or a logical right operand is skipped. |
| Function call | Root and root + 7, a perfect fifth. | A user-function frame has been entered. |
| Function return | Root, root + 7, and root + 12. | A function resolves; top-level returns receive a return cue too. |
| Loop check | Iteration-dependent accent repeats every four checks. | A repeated control-flow pattern; the trace records whether the body runs. |
| Array-valued event | Array elements are played in index order inside one event cell. | The current ordering of the emitted array value. |
| Output | A louder accent on the emitted value. | `print` appended a value to the program output. |
| Error | Root, root + 1, and root + 6. | Execution stopped with a diagnostic retained in the trace. |
| Out-of-range integer | One extra note a semitone above or below its mapped pitch. | A configured listening range was exceeded. |

Assertions use branch events. A failed assertion produces a false-branch cue
and then an error event. `break` and `continue` are branch events marked with
`data.control`; their chord alone does not distinguish them from other true
branches. Inspect the linked event for the exact operation.

For `&&` and `||`, the branch records whether the right operand runs. It is
not a direct encoding of the entire expression's Boolean result. Builtins
execute in the caller's context; only user-defined functions create call
frames. Array element writes emit their assigned value. To hear a full array
state, print the array or select an event whose value contains that array.
An empty array receives one marker note.

Depth changes both voice and register. The register cycles every three call
depths, and voices repeat after fifteen. Increasing recursion does not produce
an indefinitely rising melody. Exact depth remains visible in the trace and
call stack.

## Choose a palette and tempo

| Palette | Scale and synthesis | Useful starting point |
| --- | --- | --- |
| `classical` | Major scale; decaying harmonic tones. | Short patterns and separated events. |
| `electronic` | Natural minor scale; harmonic lead with a pulse envelope. | Distinct attacks and brighter sustained harmonics. |
| `ambient` | Pentatonic scale; longer, gently detuned tones. | Slower inspection of sparse traces. |

Their relative usefulness for debugging remains unmeasured. The WAV
synthesizer uses mathematical waveforms. External MIDI
instruments and browser Web Audio use different timbres while following the
same symbolic score.

At the default 120 BPM, one beat lasts half a second. Each event occupies
0.25 beats, so successive event cells begin 0.125 seconds apart. Array members
subdivide their event's cell. This is a musical clock: it does not measure
how long the interpreter spent executing the corresponding statement.

```sh
sonata listen lessons/fibonacci.son --wav fib-slow.wav --palette classical --bpm 80 --semantic
```

CLI tempo controls exported playback while computed results stay the same. The
browser's **Speed** control changes playback speed without recomputing a
different algorithm. A repeated pitch on the same channel releases the prior
note at its next onset. This keeps MIDI unisons unambiguous.

## Use stable motifs

Version 1 offers two mappings:

- **Semantic:** ordinary motifs derive from the function, event category,
  symbol name, statement category, and operator. Function calls and returns
  also use a deterministic function-name motif.
- **Legacy:** ordinary motifs derive from the source line number. Calls and
  returns still use their function-name motif.

The semantic mapping preserves the performance when only comments and line
wrapping change. Renaming variables or functions can change their motifs.
Two different identities can still receive the same motif because the scale
contains only a small number of degrees.

The debugger defaults to semantic mapping. On the CLI, use `--semantic` or
supply a profile. Omitting both retains the prototype's legacy mapping for
artifact compatibility. At the Python API boundary, `profile=None` means
legacy; an explicit empty profile `{}` defaults to semantic.

The formatting lessons verify equal computational traces while ignoring
source locations. The semantic performances and WAV bytes match; the legacy
performances differ. These automated checks establish representation
stability; listener recognition remains untested.

## Select what to hear with a profile

Save this JSON as `watch-total.json`:

```json
{
  "version": 1,
  "mapping": "semantic",
  "event_kinds": ["declare", "assign"],
  "functions": null,
  "variables": ["total"],
  "ranges": {"total": [0, 20]},
  "event_stride": 0.25
}
```

Then use it with the sum example:

```sh
sonata listen lessons/sum.son --profile watch-total.json --wav watched.wav
```

| Key | Accepted meaning |
| --- | --- |
| `version` | Exactly `1`. |
| `mapping` | `"semantic"` or `"legacy"`. |
| `event_kinds` | Selected event category names, such as `assign`, `call`, `return`, or `error`. |
| `functions` | Exact current function names. The top-level context is `"<main>"`. |
| `variables` | Symbol names to watch through tagged events or changes in visible snapshots. |
| `ranges` | A mapping from variable name to inclusive `[minimum, maximum]`; `"*"` supplies the fallback range. Endpoints must be signed 64-bit integers with minimum less than maximum. |
| `event_stride` | Beats per event cell, from `1/32` through `4`; default `0.25`. |

Omitted filter lists and JSON `null` impose no restriction. An empty list
`[]` mutes every event for that filter. The three filters intersect: an event
must satisfy each active filter. Lists accept at most 256 names, with at most
128 characters per name. A range map accepts at most 256 entries.

The variable filter retains events tagged with that name and events where its
visible snapshot changes, including scope entry or exit. It does not invent
new variable-sampling events. Combining it with `event_kinds: ["declare",
"assign"]` makes the accumulator lesson easy to follow. Function filtering
matches the current frame, so `"<main>"` and a function named `main` are
different selections.

Filtering leaves computation unchanged and controls which events sound.
Every original trace event and
its ID remain available. A selected note keeps its original start beat, so
muted events leave gaps. WAV export ends after the last sounding note and its
release tail; it does not pad silence through every later muted event. Filters
can also mute errors, so check the result status even when no error chord sounds.

Ranges apply to integer values carried by an event. A named range uses its
`data.name`; `"*"` handles values without a matching name, including printed
arrays. Each array member is mapped separately. The mapping distributes an
in-range value across a finite set of scale degrees. Outside values clamp to
the nearest boundary and receive the chromatic warning note. The original
integer is preserved in the trace.

The debugger exposes filters and a single named or wildcard range under
**Inputs and listening settings**. Its numeric range controls accept safe
JavaScript integers. JSON profiles used from Python or the CLI accept the
full signed 64-bit range. Set other profile details through the CLI or Python
API; the browser currently keeps a 0.25-beat event stride.

## Compare A and B around a divergence

1. Open the sum example in the debugger and expand **Compare two executions**.
2. Choose **Copy A to B**, then change B's loop end from `6` to `5`.
3. Choose **Compare A and B**, then **Go to first divergence**.
4. Enable **Loop region**. The suggested beat range covers nearby events;
   adjust **From beat** and **To beat** if you want a longer phrase.
5. Alternate **Listen to A** and **Listen to B**. They share the same beat
   position. Inspect the selected events and variables to explain the change.

The comparison matches events by ordinal position and compares their category,
values, snapshots, and stack. It ignores source locations. It does not perform
an edit-distance alignment: after an inserted event, later events may differ
at every ordinal position. An equal-trace report applies only to the two
recorded executions. Other inputs require separate investigation.

The [off-by-one comparison](../audio/v1/manifest.json) provides the exact first
divergence and a suggested beat range for the two recorded lessons. Their
recordings have different lengths because one loop performs fewer iterations.
A blinded research comparison must consider duration as a possible cue; these
teaching examples do not control away that cue.

## Edit executable music and hear the new program

Start with the sum of one through five and select **Executable score** in the
debugger. Edit the token containing the exclusive loop bound `6` to `7`, then
validate and apply the score. The editor checks the token grammar, regenerates
its notes and checksum, and executes the updated program. The new answer is
`21` because the loop now includes six.

The generated lesson performs this operation through the same score-editing
API used by the debugger. Its [manifest](../audio/v1/manifest.json) records the
changed token and actual result after MIDI re-import. You can reproduce that
last step directly:

```sh
sonata decode audio/v1/score_edited/code.mid --output edited.son
sonata run edited.son
```

This returns `21`. The decoded source is also shipped as
[decoded.son](../audio/v1/score_edited/decoded.son). General DAW edits such as
transposition or rhythmic quantization can invalidate executable scores;
use the token editor when you want a validated source edit.

## What sound cannot establish

Runtime music compresses information. Without a configured range, integer
values are reduced modulo 21 and folded into a finite register. Motif names,
source lines, and depths also have finite mappings. With a range, several
integers can quantize to the same scale degree. Different events can therefore
sound identical, and one chord is not sufficient to recover exact state.

Large arrays may be symbolically valid but too dense to distinguish by ear.
Polyphony, sustained notes, unfamiliar cues, external instrument choices,
and playback speed can all change perceptual difficulty. The audio engine's
ability to render a score does not establish that a person can follow it.

Use sound to form a hypothesis, then inspect the source, exact state, and
assertions. The [research protocol](../research/PROTOCOL.md) defines controlled
comparisons for testing whether these cues help people identify particular
classes of defects. See [ENCODING.md](ENCODING.md) for the reversible source
format, [MIDI_GUIDE.md](MIDI_GUIDE.md) for instruments and ports, and
[EMBEDDING.md](EMBEDDING.md) for programmatic configuration.
