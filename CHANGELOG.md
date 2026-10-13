# Changelog

Changes to the documented language, musical formats, and public tools are
recorded here. The [release policy](docs/RELEASE.md) defines compatibility and
verification requirements.

## 1.0.0

Version 1.0 establishes the documented language and API contracts and expands
the executable-music prototype into a packaged language, debugger, and music
integration toolkit. Human debugging effectiveness remains an experimental
research question.

### Language and reproducible execution

- Add `assert(condition);`, `break;`, and `continue;`. Loop control stays within
  the current function; assertion failures retain the partial trace and state.
- Add ordered input fixtures through `input(index)` and CLI `--inputs` files.
  Fixtures are validated, bounded, and copied before execution.
- Add checked integer helpers `abs`, `min`, `max`, and `clamp`, and bounded array
  helpers `sum`, `range`, and `repeat`.
- Add local function modules using `import name;`. The loader rejects cycles,
  duplicate names, imported side effects, and paths outside the entry directory.
  The `bundle` command emits canonical source with matching trace locations.
- Extend the independent evaluator and differential tests for the new syntax,
  builtins, and fixture semantics.
- Preserve signed 64-bit arithmetic, strict Boolean conditions, lexical scope,
  array value semantics, and bounded instruction, recursion, array, and trace
  resources.

### Executable musical source and debugger

- Preserve SC1's existing note grammar and operation pitches. New keywords use
  its identifier melodies, and bundled programs round-trip through MIDI.
- Add an editable token score that validates source edits and regenerates the
  executable notes and checksum.
- Add semantic listening profiles whose motifs remain stable across source
  formatting changes, with the original line-based mapping still available.
- Add filtering by event category, function, and watched variable while keeping
  original event IDs and timing.
- Add numerical listening ranges with explicit chromatic cues for outside values.
- Add two-run comparison, first-divergence navigation, shared-cursor A/B audition,
  and loopable playback regions.
- Improve keyboard navigation, exact integer display, asynchronous response
  handling, and narrow-layout controls.

### Music and host integration

- Add a Python music library for scales, chords, rational beat patterns, named
  voices, instrument programs, and per-voice WAV/MIDI exports.
- Add optional RtMidi ports for MIDI playback, bounded capture, timestamped
  replay, and conversion of note-on recordings into deterministic input fixtures.
- Add cooperative playback cancellation and attempted reset/all-sounds-off
  cleanup when playback ends or fails.
- Add a trace adapter for trusted synchronous Python callables, with bounded
  observations and explicit host-code execution limits.
- Retain classical, electronic, and ambient palettes synthesized from original
  mathematical waveforms.

### Packaging, documentation, and research materials

- Provide wheel and source distributions with examples and debugger assets.
  Add `sonata examples --output DIRECTORY` for installed-package lessons.
- Add tutorial, language, listening, MIDI/DAW, embedding, and release guides.
- Add 19 generated listening lessons, including a score edit whose result
  changes from 15 to 21 and a verified module example returning 55.
- Add a small usability-pilot procedure alongside the controlled study kit.
  Response templates remain empty; no human observations are fabricated.
- Add installed-package smoke checks and a configured Linux/macOS/Windows CI
  matrix for Python 3.12 and 3.14.

### Compatibility and validation scope

`assert`, `break`, `continue`, and `import` are newly reserved words. Prototype
programs using them as identifiers must rename them. User functions named after
new builtins must also be renamed. Runtime sonification remains lossy; the
canonical source score has its separate reversible contract. Playback
breakpoints inspect a completed trace rather than suspend a live interpreter.

The local build records **477 passing tests** and **596 inventoried generated
artifacts**. The v1 listening pack contains **193 files across 19 lessons**.
A native Linux RtMidi software-loopback check captured three notes and produced
the expected fixture result, **191**. Physical MIDI devices and individual DAWs
have not been tested. See the [1.0.0 release notes](docs/RELEASE_NOTES_1.0.0.md)
for evidence, installation, and remaining limits.

## 0.1.0 prototype

The local prototype introduced the reference interpreter, reversible SC1 source
scores, trace-driven MIDI and WAV, browser debugger, algorithm demonstrations,
and reproducible research kit. It established the first acceptance test: a
correct loop returned 15, an off-by-one variant returned 10, and their execution
music differed. This entry records the development baseline and does not imply
that a public 0.1.0 release was published.
