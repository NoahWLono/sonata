# SONATA 1.0 implementation and release plan

The user authorized the full feature expansion discussed on 2026-10-13 and a
new public GitHub repository, after implementation and verification. Work stays
local until the release gate below passes. The intended audience is programmers,
educators, researchers, and artists investigating computation through sound.

## Scope and contracts

1. Extend the language with assertions, break/continue, bounded math/array
   helpers, reproducible input fixtures, and local source modules. Keep signed
   64-bit arithmetic and explicit execution limits. Preserve independent
   evaluation and executable MIDI round trips for bundled programs.
2. Add selective listening, stable configurable mappings, two-run comparison,
   looping, and an editable musical-source token score to the browser debugger.
   This remains recorded execution navigation; do not describe it as an
   interpreter suspended at a breakpoint.
3. Provide a small deterministic Python music library, optional MIDI port
   playback and capture/replay, per-voice export, and an explicit trace adapter
   for trusted Python callables. Core installation must work without MIDI
   hardware or its optional native backend.
4. Deliver a progressive language and listening manual, MIDI/DAW walkthrough,
   embedding documentation, accessible controls, reproducible examples, and
   a practical pilot-study package. No participant results are invented.
5. Build versioned wheel/sdist distributions, package example resources,
   establish a cross-platform CI matrix, and verify installed-package behavior.

Runtime fixture API: `execute(ast, limits=None, inputs=None)`; inputs are an
ordered JSON array of supported language values, read by `input(index)`.
All host-side integrations validate external data before producing traces or
notes. SONATA source never gains host Python evaluation or unrestricted I/O.

The existing source codec remains readable. New syntax must be encoded through
actual notes and preserve canonical ASTs after module bundling. Runtime profiles
are versioned independently of the executable source codec. Filtering must keep
original event IDs and an explicit time mapping.

## Ownership and sequence

- Language lane: parser, interpreter, independent evaluator, codec changes,
  module loader, language tests/spec and language examples.
- Music lane: music profiles, filtering/comparison APIs, music utilities,
  live MIDI adapter, Python trace adapter, focused tests/integration guide.
- Debugger lane: browser assets only, UI tests/manual, coordinated server API.
- Integration lane: CLI/server, packaging, manuals, release evidence, complete
  verification and review. Shared files are changed by their owner.

Write meaningful failing tests before behavior changes. Integrate the lanes,
run targeted regression tests, then run the complete build. A separate reviewer
audits the integrated result and fixes receive focused regression coverage.

## Release gate

- [x] Every scoped feature is implemented, demonstrated, and documented.
- [x] Full tests, independent evaluator comparisons, source-MIDI round trips,
      runtime MIDI checks and WAV energy/duration checks pass.
- [x] Browser workflows are exercised, including comparison, score editing,
      filtering, export, keyboard use, and narrow layouts.
- [x] Wheel and sdist install in fresh environments; examples and web assets
      are present; documented quick-start commands run outside the checkout.
- [x] Generated demonstrations and study materials are rebuilt and verified.
- [x] Review findings are resolved; no secrets or machine-specific private
      paths are included in the release.
- [x] Limitations identify physical-device/DAW/OS tests actually performed,
      measured automated results, and the absence of human study results.

After these local gates pass, commit the verified tree, create the new public
repository, and push `main`. Wait for its CI matrix before tagging `v1.0.0` and
publishing the release assets. Verify the remote commit/tag and downloaded
artifact hashes. These remote results belong to the Actions run and release;
they cannot be established by a local build.

## Progress

Baseline: local commit a14a060, previously verified prototype with 311 tests.
The integrated v1 build passes 477 tests and reproduces 596 generated files.
See [the final verification record](verification/V1_RESULTS.md).
