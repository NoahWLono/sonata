# Research questions: current evidence and open work

The implementation and automated experiments establish executable behavior,
symbolic score recovery, and signal differences. No people have been tested.
Generated assignments specify future trials. The measured
report is `experiments/results/analysis.json`; its `missing_demos` field defines
which demonstrations were unavailable in that run.

## 1. Can a programmer recognize a function execution pattern as readily as a musician recognizes a melody?

**Unanswered.** Repeated events produce deterministic motifs, and linked notes
allow the debugger to identify the corresponding source. Determinism does not
establish recognition speed, memory, or recognition by ear. A trained-versus-
untrained recognition study with unseen functions and controlled exposure is
needed. The present debugging pilot would provide only indirect evidence.

## 2. Can recursion be represented harmonically without overwhelming the listener?

**Partially implemented; listener burden is unanswered.** Calls add a fifth,
returns add a cadence, and depth changes register and voice. The renderer can
produce the bounded recursive demonstrations. Registers and channels repeat,
so deep recursion does not have a unique harmonic identity. PCM energy and
spectral centroid describe the output signal. A study must assess perceptual overload. A
listening study should vary depth, tempo, and density separately and collect
accuracy and workload.

## 3. Are specific bug classes especially amenable to auditory detection?

**Unanswered for people.** The off-by-one experiment measures the first
structural and musical divergence and a change in event count. Bounded
non-progressing loops and growing recursion generate different event sequences
and resource-error chords. Such differences supply candidate cues; they do not
show detection rates. The kit supplies five task families and a coded listening
pair for a future study, with duration as an acknowledged possible shortcut.

## 4. Does musical experience influence effectiveness?

**Unanswered.** The protocol records musical and programming background and
requires equal training. No subgroup effects are estimated from empty response
files. Musical training, active practice, programming experience, and prior
sonification exposure should be distinguished when enough observations exist.

## 5. Could nonvisual programming interfaces benefit?

**A plausible application that this prototype has not evaluated.** The system
can emit computation-linked audio, but the implemented editor and study tasks
require visible source. The current study cannot establish accessibility for
blind or low-vision programmers. Co-design and testing with intended users,
keyboard operation, screen-reader access, and nonvisual state inspection would
be necessary before that claim.

## 6. Can a musical representation be pleasant, expressive, and losslessly executable at the same time?

**Symbolic executability is demonstrated separately from pleasantness.** SC1
stores source tokens, operands, and a checksum in note events; the experiment
compares recovered canonical ASTs. The expressive runtime mapping has explicit
collisions. They prevent lossless source recovery. The source
score's use of notes does not establish pleasantness, and no test here recovers
source from raw audio. Combining subjective musical quality with reliable
human decoding remains an open design problem.

## 7. What information must remain visual or symbolic because sound communicates it poorly?

**The implementation identifies omitted information.** It does not establish a universal
perceptual limit. The pitch and rhythm candidates retain event kind but discard operands,
source positions, variables, and stacks. The expressive mapping repeats value
degrees modulo 21 and source motifs by scale length, and depth voices recur.
Exact integers, identifier spelling, arbitrary arrays, and full state therefore
require the source score or debugger state in this implementation. Future
encodings could communicate more; whether they remain practical to hear is
unmeasured. Current collision metrics should not be generalized into claims
about what human hearing can never convey.
