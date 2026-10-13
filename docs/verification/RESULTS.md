# Verification record

The complete `bash scripts/build.sh` run succeeded. Its captured output is
[`build.log`](build.log). The final suite passed **311 tests**.

The build first ran the milestone acceptance test, then generated its recordings,
ran the complete suite, regenerated all eight demonstration bundles, analyzed
seven research demonstrations, generated the study kit, rendered the video, and
re-read the saved artifacts. The final check verified eight program bundles and
created an inventory of 383 generated files in `audio/SHA256SUMS`.

A second complete artifact regeneration reproduced all **383 inventoried files
byte for byte**. `checksums.log` records the comparison against the earlier
inventory; `reproduction.log` records the generation commands' output. This
includes the optional MP4 in the same host environment. A final suite run again
passed all 311 tests after the agents finished their changes.

## Evidence

- Seven successful demonstration programs pass the independent evaluator and
  complete source-note-MIDI-AST round trip. The deliberate off-by-one program
  is included: both evaluators compute its incorrect-for-the-task result, 10.
- The eighth bundle is intentional runaway recursion. It terminates at call
  depth 12 with a structured error, and its canonical AST survives the round trip.
- The first milestone computes 15 versus 10, with 40 versus 34 execution events
  and 42 versus 36 musical notes. WAV lengths are approximately 5.185 and 4.435
  seconds; actual PCM energy is nonzero.
- The source codec test removes all MIDI metadata and still reconstructs the
  AST and result. Another test exhaustively enumerates 123 bounded expressions
  with no note-score collisions in that domain.
- All three palettes have note-interval round-trip tests. Dense-array tests
  exercise 128, 256, and the configurable maximum 4,096 elements.
- HTTP tests exercise real execution, WAV and both MIDI exports, invalid input,
  origin restrictions, and exact transport of integers beyond JavaScript's
  numeric precision.
- FFprobe identifies the showcase as 1280×720 H.264 video with AAC audio,
  lasting 11.633 seconds after video-frame rounding. A decoded frame was
  visually inspected and is saved as `showcase-frame.png`.

The study kit has 30 verified stimuli, six counterbalanced sequences, 90 assigned
trial packets, two coded listening clips, and **zero observed participant rows**.
Assignments are balanced across condition, variant, family, and normal/abnormal
status within the six-sequence unit. These generated schedules contain no
empirical participant results.

## Independent review and corrections

A separate agent reviewed the interpreter, reference evaluator, source codec,
MIDI boundary, verifier, server, frontend, and study design. It ran bounded local
probes and made no repository edits. Its findings led to regression tests and
the following corrections:

| Finding | Correction |
| --- | --- |
| Deep source expressions compiled into undecodable scores | Precedence-aware printing preserves AST structure without redundant nesting |
| Indentation expanded valid source beyond the parser limit | Compact score formatting retains line structure without indentation |
| The browser rounded large signed integers | Tagged exact integers cross the JSON boundary and render exactly |
| Condition A always received the smallest study variant | Independent variant rotation and complete balance assertions |
| Ambient repeated notes changed durations in MIDI | Same-key retrigger articulation; generic ambiguous overlaps rejected |
| Array-index side effects updated a replaced array | Specified RHS → index → current binding order, implemented independently in both evaluators |
| Reference rejected unary plus and loop-variable shadowing | Correct unary typing and a separate loop-body environment |
| Malformed MIDI reached an unbounded general parser | Byte, track, event, timing and four-byte-VLQ preflight limits |
| Empty MIDI exposed a traceback | Structured CLI failure |
| Alternate trial spellings bypassed duplicate detection | Normalize trial numbers before duplicate checks |
| Palette changes could race pending execution | Busy-state disabling and request consistency checks |

A subsequent dense-array probe found that 480 PPQ could merge successive
notes into the same tick. MIDI storage now uses 30,720 PPQ, and the maximum-array
export regression passes. These local correctness checks have bounded coverage.
An exhaustive security audit has not been performed.

## Practical limits

The reference evaluator shares the parser, and MIDI writer/reader both use Mido.
The verification report records these shared dependencies. Browser controls
navigate a bounded, completed trace. They do not suspend a live interpreter or
modify paused execution state. Runtime music intentionally loses information;
its measured collisions are in `experiments/results/analysis.json`.

The two synthesizers use the same semantic notes but different timbres. Tests
establish deterministic file output within this pinned environment. No human
listening study, accessibility evaluation, cross-platform bitwise audio proof,
or auditory WAV-to-source transcription has been performed.
