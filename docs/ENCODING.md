# Musical encoding design

SONATA uses an exact symbolic score for source and a compressed performance for
runtime behavior. The two layers optimize different tasks.

## SC1 executable score

SC1 represents the tokens of `format_source(AST)`. Comments, whitespace and
source locations are discarded; the canonical AST preserves computation.
The supported domain is valid SONATA ASTs whose canonical source passes the
parser's limits and whose score contains at most 100,000 notes.

Every cell lasts 1/8 of a quarter-note beat, equivalent to 60 ticks at 480 PPQ.
Notes last 3/32 beat, equivalent to 45 ticks at 480 PPQ. MIDI files use 30,720
PPQ so runtime arpeggios can represent even the maximum 4,096-element array
without collapsing repeated notes onto one tick. The first cell is the chord
`[96, 100, 103]` on channel 0, and the
last is `[95, 99, 102]`. Interior cells contain exactly one note.

Syntax tokens, in this exact order, use channel 0 and MIDI pitches 36 through 71:

```text
let for in if else while fn return true false print len
{ } ( ) [ ] ; , = .. + - * / % == != < <= > >= && || !
```

An identifier starts with pitch 84, and a decimal integer starts with pitch 85.
Its ASCII bytes are each split into high and low four-bit digits. These digits
use channel 1 and the following diatonic pitches:

```text
digit:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
pitch: 48 50 52 53 55 57 59 60 62 64 65 67 69 71 72 74
```

Pitch 86 on channel 0 ends the operand. Pitch 87 introduces eight checksum
digits on channel 2, using the same digit pitches. The checksum is CRC32 of
the decoded tokens joined with one ASCII space. Its purpose is accidental
corruption detection. It is not authentication, and CRC32 collisions exist.

Decoding rejects missing or additional cells, wrong rhythmic lengths, malformed
operands, unknown operation notes, checksum mismatch, and invalid source.
Tempo changes and instrument/velocity changes preserve the symbolic program.
Transposition and timing edits generally invalidate it. This quantized grammar
requires exact rhythmic alignment.

### Why the encoding is reversible on its stated domain

The operation and operand states have disjoint channel/pitch alphabets. A
channel-0 delimiter cannot be confused with a channel-1 operand digit. All
16 digit pitches are distinct, so each pair recovers exactly one byte. The
operation table is one-to-one, and framing fixes the order of cells. Thus a
valid encoded token sequence has a unique decoded token sequence. Parsing the
canonical token sequence reconstructs its AST after source locations are
removed.

This finite-format argument covers SC1 alone. Pleasantness and human perception
require different evidence. The test suite exercises generated programs,
metadata removal, deterministic files, corruption, and full example programs.
The checksum is additional validation and is not needed for the uniqueness
argument. Scores that exceed the resource bounds are outside the reversible
domain. No claim is made about reconstructing a program from WAV audio.

`test_exhaustive_bounded_expression_note_alphabet` enumerates all 123 expressions
in a stated small grammar: 11 integer binary operators on `{-1, 0, 1}`, unary
signs on those integers, four Boolean binary operators on both Boolean values,
and Boolean negation. All scores differ and recover the same canonical AST.
Some of these expressions intentionally raise runtime errors, such as division
by zero; their syntax still round-trips. This enumeration covers that finite
grammar only.

## Runtime performance

Each trace event advances musical time by 0.25 beats, or 0.125 seconds at
120 BPM. Every event produces at least one note. Array values distribute
member notes within that event's cell. Ambient notes sustain beyond their cell.
Harmony and register carry event type and call depth; event JSON retains the
exact source location and full variable snapshot.

The mapping compresses numerical values modulo 21 and source locations modulo
the palette's scale length. Depth changes register modulo 3 and voice modulo
15. Consequently many different computational events sound alike. Pitch
clipping, repeated values, polyphony and fast arrays introduce further limits.
The runtime MIDI retains a musical trace; it omits part of the program state.

The classical palette uses a major scale and decaying harmonic synthesis. The
electronic palette uses a minor scale and synthesized harmonic waveforms. The
ambient palette uses a pentatonic scale and longer envelopes. Timbres are
original oscillators; no recorded instrument assets are distributed.

A repeated pitch on the same voice releases its preceding note at the new
onset. This articulation keeps note intervals unambiguous in MIDI, including
the ambient palette; other pitches can continue to sustain. The generic MIDI
writer rejects overlapping same-pitch/same-channel notes supplied directly.
Dense arrays are symbolically exportable but may be too fast to distinguish
by ear. Maximum array size bounds computation. It says nothing about perception.

## Candidate mappings and selection

The executable comparison in `experiments/analyze.py` measures three mappings.
Pitch and rhythm candidates encode event category; the polyphonic candidate
is the debugger's runtime mapping. Their domain and recovery claims are stated
in the generated result, so a category decoder is not mistaken for full-state
recovery.

| Criterion | Pitch categories | Rhythm categories | Polyphonic runtime |
| --- | --- | --- | --- |
| Density | One category per note | Category needs a distinguishable duration | Several properties share a cell |
| Symbolic decoding | Exact within reserved alphabet | Exact on the duration grid | Full event recovery unavailable |
| Musical organization | Stable repeated pitches | Stable rhythm vocabulary | Scales, voice changes, chords and arpeggios |
| Ambiguity | Operands and source state omitted | Tempo/grid handling matters | Deliberate value/location/depth collisions |
| Anomaly cues to test | New category pitch | Changed rhythm | Missing phrase, changed harmony or density |

SC1 was selected for executable source because its grammar can be checked
precisely. The polyphonic mapping was selected for the debugger because it
can expose several execution properties in a short passage. Musical
intelligibility, comfort, and comparative debugging effectiveness remain
human-study questions. The table states engineering properties and hypotheses.
Listener preferences have not been measured.

Standard MIDI serialization follows Mido's documented beat/tick model. See
[Mido MIDI file documentation](https://mido.readthedocs.io/en/1.2.10/midi_files.html).
