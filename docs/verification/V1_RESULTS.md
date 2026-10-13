# SONATA 1.0 verification results

The full local build passed **477 tests** on CPython 3.14 and Linux. It verified
11 demonstration bundles and inventoried **596 generated files**. A second
generation reproduced all 596 files byte for byte in the same pinned environment,
including the showcase video. The logs are [v1-build.log](v1-build.log) and
[v1-reproduction.log](v1-reproduction.log). Local checkout paths in these logs
are replaced with `<checkout>`; the test results and checksums are unchanged.

## Language and musical representations

- The first milestone still computes 15 for the correct loop and 10 for its
  off-by-one variant. Their traces, note structures, and audio differ.
- Tests cover parsing, lexical scope, strict typing, checked arithmetic,
  functions, recursion, loops, arrays, assertions, loop control, fixtures,
  source modules, error paths, and execution limits.
- Musical source tests compare canonical ASTs and behavior after SC1 MIDI
  export and re-import. Removing MIDI metadata does not erase the program.
  Bounded exhaustive and seeded randomized tests supplement fixed examples.
- An independently implemented evaluator checks computational results. It
  shares the parser and module bundler; this is not complete implementation
  independence. MIDI serialization and import share Mido.
- Tests reread generated WAV samples for duration and energy, recover MIDI
  intervals, and match musical event IDs to actual source-located trace events.

The [v1 listening lessons](../../audio/v1/manifest.json) contain 19 clips and
193 files. Formatting-only source changes produce identical semantic notes
and WAV bytes, while the legacy mapping can change. A musical-score bound edit
from 6 to 7 changes the sum from 15 to 21 and retains that result after MIDI
re-import. The module example returns 55 under both evaluators. Filtering keeps
event identity and timing. Array lessons preserve the actual intermediate
states and finish with ascending pitches.

## Browser and integrations

The actual in-app browser was exercised against the local release server:

- The sum/off-by-one comparison reports 15 versus 10 and navigates to the first
  semantic difference; switching audition retains the shared cursor.
- Editing a source-score token from 15 to 21 updates the program. Its downloaded
  executable MIDI decodes and returns 21 through the CLI.
- A JSON fixture containing 9007199254740993 retains that exact integer through
  execution and display. A return-only filter starts with event zero's state.
- Playback loops, speed changes, stepping, and source breakpoints work. A
  breakpoint on line 4 pauses at event 6 of the sum trace with `total=0, i=1`.
- Desktop and narrow layouts were inspected; the narrow rendered document had
  equal client and scroll widths, with no horizontal page overflow. Browser
  console inspection returned no warnings or errors for the tested workflows.

Screenshots: [desktop](debugger-v1.jpg), [narrow layout](debugger-v1-narrow.jpg).
The automated Node harness also covers pending-request races, comparison state,
empty traces, invalid score drafts, muted selections, and loop endpoints.

The [native MIDI loopback test](midi-loopback.json) sent and captured the notes
60, 64, and 67 through a temporary Linux RtMidi port. Converted fixtures replay
deterministically and return 191. No physical instrument or DAW was tested.
The optional native backend is unnecessary for default installation and playback.

A user-supplied standard MIDI sequence imported 1,279 notes across five tracks.
Its 84.380868-second channel stream was tempo-scheduled through an in-memory
port. The [compatibility record](user-midi.json) preserves counts and the input
hash. The third-party sequence is excluded from the public distribution because
its redistribution license was not established.

## Release packages and review

The [package smoke report](package-smoke.json) records SHA-256 values and
fresh-environment checks for the wheel and source archive. Installation checks
run outside the repository, exercise packaged examples, fixtures, modules,
MIDI round trips, WAV synthesis, composition/stems, Python tracing, recorded MIDI
fixtures, independent verification, web resources, and a loopback debugger server.

The [review record](V1_REVIEW.md) describes corrected findings and the re-review.
GitHub Actions runs six OS/Python combinations after publication. The local
evidence above does not claim those remote jobs have already completed; consult
the repository's Actions results for their status.

## Research limits

The kit contains 30 study stimuli, six counterbalanced sequences, 90 assigned
trial packets, empty response forms, and **zero observed participant responses**.
Automated differences and collisions are measured in
[the signal analysis](../../experiments/results/analysis.json). They cannot
establish improved human recognition, debugging speed, confidence, workload,
or accessibility. [The pilot](../../research/PILOT.md) and
[controlled protocol](../../research/PROTOCOL.md) describe the next experiments.

Runtime sonification is lossy. Exact machine decoding applies to the specified
SC1 symbolic domain, not to a listener's interpretation or to rendered WAV.
Floating-point PCM identity across operating systems, physical MIDI routing,
individual DAWs, screen-reader usability, and human outcomes remain unverified.
The debugger navigates completed bounded traces. The Python adapter executes
trusted synchronous host code and cannot interrupt blocking native operations.
