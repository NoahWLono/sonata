# Reproduce the mapping measurements

Run these commands from the repository root after building `audio/demos`:

```sh
.venv/bin/python experiments/analyze.py --root .
.venv/bin/python scripts/study.py generate --root . --participants 6
.venv/bin/python scripts/study.py analyze research/responses.template.csv
```

`run_analysis(root)` in `experiments/analyze.py` returns its report and writes
`experiments/results/analysis.json`. Missing demonstration files are listed in
`missing_demos`; they are never counted as measured. Input hashes identify the
recordings, traces, notes, and musical source used by each run. The analysis is
deterministic for unchanged inputs and library versions.

## Three implemented mappings

The mapping labels below are separate from the study's interface conditions.

| Mapping | Implemented representation | Decoder and loss |
| --- | --- | --- |
| A, pitch | One note per event in a half-beat cell. The ten event kinds use pitches 48, 50, …, 66. | Pitch identifies kind exactly in the symbolic score. Operands, locations, variable snapshots, and stack are omitted. |
| B, rhythm | One pitch, 60. Duration is `(kind_index + 1) / 32` beats in a half-beat cell. | Duration identifies kind when the time scale is known. It omits the same state as A. Coarse duration quantization can merge symbols. |
| C, polyphonic | The application's classical `sonify` function, including branch chords, return cadences, array arpeggios, and depth voices. | There is no general decoder. Values, source lines, and call depths repeat in the finite musical vocabulary. |

Event-kind order is `statement, declare, read, assign, loop, branch, call,
return, output, error`. A and B are functioning comparison encoders with MIDI
exports in `results/mapping_scores`. C uses the notes exported by the application;
the report checks that they equal a fresh `sonify(trace)` call.

## What the numbers mean

An **event identity** consists of kind, line, column, call depth, function name,
and event data. It excludes sequence ID, the complete variable snapshot, and the
stack list. A **musical signature** contains each event's pitches, relative
onsets, durations, velocities, and channels. It excludes source metadata and
absolute onset. Grouping the notes by event uses the known trace linkage. This
is an oracle for measuring information loss; it does not demonstrate recovery
of event boundaries from a recording.

An identity collision group contains at least two distinct event identities
with the same signature. A kind collision group contains at least two kinds.
`oracle_kind_majority_accuracy_on_this_corpus` is the fraction obtained by
guessing the most frequent kind for each observed signature. It uses the same
corpus to form and score groups. It is neither a trained decoder's held-out
accuracy nor a listening result. Zero observed collisions in a small example
does not establish injectivity.

For a concrete C collision, assignments at lines 1 and 8 with values 1 and 22
have the same classical motif and value degree at equal depth. The test suite
checks this collision. Return cadences also omit their returned value. The
metadata in `notes.json` preserves the original event link for the debugger,
but those metadata fields do not make the sound itself reversible.

The A/B experiment decodes the original notes and a MIDI round trip, then
changes MIDI tempo to 60 and 180 BPM. MIDI beat positions remain stable under
tempo changes. A separate perturbation rounds times and durations to a
one-eighth-beat grid. These transformations operate on symbolic scores.
Perceptual tolerance and acoustic transcription quality are unmeasured. C's perturbation
measurement counts changed per-event signatures.

## Source-code recovery is a separate test

Each demonstration's `code.mid` is decoded using SC1 and compared with the
canonical AST of its source. SC1 encodes program tokens, operands, framing, and
a checksum in note events. Exact symbolic source recovery does not imply that
the runtime sonification is reversible, that a person can read the score by
ear, or that an audio recording can be transcribed losslessly. Whitespace and
comments are intentionally outside the canonical AST comparison.

## Signal measurements

The script reads the actual 16-bit PCM WAV files. It reports duration, sample
rate, frame count, peak amplitude, normalized RMS, and the sum of squared
normalized samples. The spectral centroid uses 2,048-sample Hann windows, a
1,024-sample hop, and global power weighting, after a mono downmix. These
quantities describe signal content. They do not measure pleasantness,
comprehensibility, perceived loudness, or accessibility.

For the sum/off-by-one pair, the report gives the first differing event content
and first differing musical event signature using zero-based indices, plus
event and note count differences. Listening discrimination requires the
separate study described in `research/PROTOCOL.md`.
