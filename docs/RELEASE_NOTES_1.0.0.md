# SONATA 1.0.0 release notes

SONATA 1.0.0 combines a bounded programming language, executable musical source
scores, and a local audible debugger. Write an algorithm, run it, and follow
its control flow and state changes through synchronized source, trace, and
sound. Edit the algorithm or its musical token score, then compare executions.

The version number establishes the documented software contracts. Whether
sonification helps people debug more accurately, quickly, or comfortably
remains an open research question. No participant results have been collected.

## Install and start

Python 3.12 or later is required. Create a virtual environment and install
from an extracted source archive or checkout:

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install .
sonata examples --output lessons
sonata run lessons/sum.son
sonata debug --open
```

A downloaded wheel installs directly from its local path:

```sh
python -m pip install ./sonata_lang-1.0.0-py3-none-any.whl
```

The debugger listens at `http://127.0.0.1:8765` and includes its own assets and
examples. If automatic browser opening is unavailable, visit that address.
The terminal must stay open while the server runs. Use `--port 8766` to choose
another port. Core execution, MIDI files, and WAV export need no account,
proprietary sound library, MIDI hardware, or DAW. These installation commands
do not assume a PyPI publication.

For optional native MIDI ports, install the extra from the checkout:

```sh
python -m pip install '.[midi]'
sonata midi ports
```

Port availability depends on the operating system and installed backend.
The [MIDI guide](MIDI_GUIDE.md) explains routing, capture, replay, and input
conversion. SONATA does not install a DAW or configure its audio system.

## Language features

The language supports signed 64-bit integers, strict Booleans, copied integer
arrays, lexical blocks, arithmetic, conditions, `for` and `while` loops,
first-order functions, returns, and recursion. Version 1 adds:

- Assertions that stop at the failed condition and preserve the partial trace.
- `break` and `continue`, restricted to loops in the current function.
- Validated external JSON fixtures, read through `input(index)`.
- Integer helpers `abs`, `min`, `max`, and `clamp`, plus bounded `sum`, `range`,
  and `repeat` array helpers.
- Local function modules, resolved and bundled before execution or compilation.

Every run has explicit resource bounds. Source programs do not gain host
Python execution, network access, arbitrary file I/O, or wall-clock operations.
The [language guide](LANGUAGE_GUIDE.md) teaches the features, and
[SPEC.md](../SPEC.md) gives the grammar, type rules, evaluation order, limits,
and structured error contracts.

## Two musical representations

**Executable source MIDI** uses actual notes to encode canonical source tokens.
Its grammar, operand melodies, and checksum support MIDI-to-AST reconstruction.
Bundled modules produce a self-contained score. External input fixtures remain
separate and must be supplied again to reproduce an input-dependent execution.

**Execution music** follows the events of one run. Calls, returns, branches,
array values, updates, and errors receive deterministic musical structures.
Classical, electronic, and ambient palettes use original synthesis. The
runtime mapping compresses state; exact values remain available in the trace.

```sh
sonata listen lessons/sum.son --semantic --wav sum.wav --midi sum.runtime.mid
sonata compile lessons/sum.son --midi sum.code.mid
sonata decode sum.code.mid --output recovered.son
sonata run recovered.son
```

The recovered source returns **15**. Source formatting and comments need not
survive canonicalization. Runtime MIDI and WAV do not reconstruct source.
See the [encoding design](ENCODING.md) for the reversible domain and its tests.

## Debugger and listening tools

The local debugger includes source editing, trace stepping, playback
breakpoints, variable snapshots, a call stack, note/source selection, playback
speed, and exports. Version 1 adds:

- A musical token editor that validates edits and regenerates SC1 notes and
  checksums. The recorded lesson changes a loop bound from `6` to `7`, then
  verifies that MIDI re-import computes **21** instead of **15**.
- Two-program or two-fixture comparison with a shared cursor, first-divergence
  navigation, A/B audition, and repeatable listening regions.
- Semantic motifs that survive formatting changes, alongside the original
  source-line mapping.
- Event, function, and variable filters that preserve original event timing
  and IDs, plus numerical ranges with out-of-range warning notes.
- Keyboard controls, exact 64-bit state display, and layouts for narrow screens.

The interpreter completes its bounded execution before playback starts.
Playback breakpoints navigate the recorded trace; editing state during a live
suspended execution is outside version 1.0.

```sh
sonata compare lessons/sum.son lessons/off_by_one.son --wav-dir comparison --semantic
sonata run lessons/fixtures.son --inputs lessons/fixtures.json
sonata bundle lessons/modules/main.son --output module.bundle.son
sonata verify lessons/modules/main.son --report module-verification.json
```

The off-by-one example returns **10**, the fixture example **16**, and the
module example **55**. The [debugger manual](../debugger/README.md) documents the
controls. The [listening guide](LISTENING_GUIDE.md) links to all 19 recorded
lessons and explains exactly what the cues do and cannot reveal.

## Music and Python integration

The Python music library provides scales, chords, exact rational beat patterns,
named voices, instrument selection, and separate voice stems. Execution-derived
notes can be exported with the same WAV and MIDI tools.

Optional native MIDI ports provide file playback, bounded input capture, and
replay of timestamped channel messages. Recorded positive-velocity note-on
messages can become pitch, velocity, and microsecond-time arrays consumed by
SONATA fixtures. Playback attempts reset and all-sounds-off cleanup on normal
completion, cancellation, and failure.

The Python trace adapter observes trusted synchronous callables and maps their
recorded behavior into the same sonification pipeline. It runs ordinary host
Python with host permissions. It is not a sandbox, and its observation bounds
cannot interrupt blocking native calls or control other threads. See the
[embedding guide](EMBEDDING.md) for API contracts and runnable examples.

## Verification available for this release

| Evidence | Result and scope |
| --- | --- |
| [Full local build](verification/v1-build.log) | **477 tests passed**; the build inventoried **596 generated artifacts**. |
| [Artifact reproduction](verification/v1-reproduction.log) | Regenerated outputs matched the saved checksum inventory in the pinned local environment. Cross-platform PCM byte identity is not promised. |
| [Listening lesson manifest](../audio/v1/manifest.json) | **19 lessons, 193 files**; includes traces, notes, MIDI, WAV, source, fixtures, profiles, and validation. |
| [Distribution smoke checks](verification/package-smoke.json) | Wheel and source archive installed in fresh environments and exercised outside the checkout, including examples, fixtures, modules, MIDI round trips, WAV, verification, and debugger resources. |
| [Native MIDI loopback](verification/midi-loopback.json) | A temporary Linux Mido/RtMidi software port captured notes **60, 64, 67**; the derived fixture returned **191**. |
| [External MIDI compatibility check](verification/user-midi.json) | A user-provided sequence containing **1,279 notes** was parsed and tempo-scheduled through an in-memory port and virtual clock. The third-party sequence is not bundled. |

The configured GitHub Actions matrix covers Python 3.12 and 3.14 on Linux,
macOS, and Windows. Its presence is not evidence of completed remote jobs;
the results above describe local verification. Publication and remote checks
follow the [release procedure](RELEASE.md).

Independent evaluation shares the parser and consumes the same bundled source.
The verification pipeline also shares MIDI and numerical dependencies. Tests
cover these interfaces and corruption cases, but they do not constitute a
formal proof of the entire toolchain. No physical MIDI device or individual
DAW has been tested, and the software-loopback result does not establish their
compatibility or latency.

## Compatibility and remaining boundaries

SC1's existing operation pitches and note grammar are preserved. Version 1
keywords use its existing identifier melodies. Prototype programs that used
`assert`, `break`, `continue`, or `import` as identifiers must rename them.
Functions named after new builtins must also be renamed.

The documented trace, profile, recording, and Python-adapter contracts are
versioned. Incompatible changes require a major version or an explicit new
format identifier under the [compatibility policy](RELEASE.md). Runtime
sonification remains lossy: motif collisions, finite registers, quantized
ranges, and dense polyphony can make distinct behavior sound alike.

SONATA does not provide a full DAW, plugin host, native optimizing compiler,
concurrent source execution, or hard real-time guarantees. The localhost
debugger is intended for local development. Captured MIDI timestamps and live
playback include operating-system scheduling jitter; recorded message order
and scheduled relative times are reproducible.

The [usability pilot](../research/PILOT.md), [controlled study protocol](../research/PROTOCOL.md),
counterbalanced stimuli, empty response forms, and analysis scripts support
future human evaluation. Programming education, research, and computational
art are current uses. Benefits for everyday debugging or nonvisual interfaces
require participant evidence.

## Where to start

- [Tutorial](TUTORIAL.md): install, run, listen, introduce a defect, and recover
  source from executable MIDI.
- [Language guide](LANGUAGE_GUIDE.md): learn the syntax and execution model.
- [Listening guide](LISTENING_GUIDE.md): practice the cues with verified clips.
- [Debugger manual](../debugger/README.md): inspect and compare executions.
- [MIDI/DAW guide](MIDI_GUIDE.md): export parts, connect ports, and replay inputs.
- [Embedding guide](EMBEDDING.md): use the interpreter, music library, and trace
  adapter from Python.
- [Changelog](../CHANGELOG.md): changes from the local prototype.

Original project code and synthesized music use the [MIT license](../LICENSE).
Third-party dependencies retain their own licenses. Reproduce the local build
with `bash scripts/build.sh`; distribution-specific checks are documented in
[RELEASE.md](RELEASE.md).
