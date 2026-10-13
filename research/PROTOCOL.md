# SONATA debugging pilot protocol

This kit prepares an exploratory within-participant comparison. It contains
generated task assignments and verified program stimuli, with **zero participant
observations**. The preparation scripts do not recruit people, record consent,
or infer human performance from program output.

## Question and interventions

Does the available representation affect how a programmer identifies abnormal
behavior in a small program? Compare these interfaces while keeping each task's
source and intended behavior visible:

| Condition | Available evidence |
| --- | --- |
| A | Source and a textual execution log |
| B | Source and execution audio |
| C | Source, execution audio, and a clickable event timeline linked to source lines |

All three use the same runtime and language semantics. Conditions B and C use
the classical polyphonic mapping at 180 BPM and 11,025 Hz. This study compares
interfaces. It does not directly compare the pitch-only and rhythm-only mapping
candidates in `experiments/analyze.py`.

## Tasks and counterbalancing

The generator creates five task families: an omitted final addend, a loop whose
counter does not progress, recursion moving away from its base case, a reversed
threshold branch, and normal/abnormal array accumulation. Each family has three
parameter variants and a correct and defective version, for 30 unique sources.
Every stimulus is executed during generation. Correct stimuli must return the
specified result; defective stimuli must produce the specified wrong branch,
different result, or bounded resource failure.

Each participant receives 15 tasks: five per condition, one from each family.
The participant sees each parameter variant only once per family. They never
receive both members of an identical correct/defective pair. Assignment rotates
the variant and family order. Six participant sequences use `ABC, BCA, CAB,
ACB, CBA, BAC`, two complementary Latin squares. Every condition appears equally
often in each block across six sequences. Parameter variants rotate independently
of the block order. Each condition/variant/family combination has one correct
and one defective trial within a six-person unit. Complete six-person sequence sets
before interpreting aggregate condition differences; an incomplete set is
reported as incomplete.

The variants share program structure. Their relative difficulty has not been measured.
The programming error can still be inferred from visible source. Distinct
parameters reduce exact repetition but do not eliminate transfer between
related tasks. Treat these factors as limitations and inspect results by
family, variant, and order. A larger confirmatory experiment requires piloting
the materials and a sample-size plan based on an independently chosen effect
and uncertainty target. Six generated sequence IDs are not a power analysis.

## Preparation and separation of materials

Run `python scripts/study.py generate --participants 6`. Open the generated
`research/participant/P001/index.html` locally to inspect one sequence. The
condition-specific HTML includes only the evidence assigned to that trial.
The generator also writes `research/researcher_only/assignments.csv`, verified
stimulus traces, and `answer_key.json`.

Before distributing materials, copy only the assigned participant directory
and the participant instructions to a separate location. Keep the entire
`researcher_only` directory, source repository, generated assignments, filenames
from `audio/demos`, and answer keys inaccessible during the session. Coded
labels do not conceal answers from someone who has the repository or lookup
tables. Directories separate the materials; the experimenter controls access.
An experimenter must enforce the condition and sequence. No participant portal
or tamper-resistant data collection is claimed.

Do not overwrite collected CSV files with generated templates. The generator
writes only `responses.template.csv`, which contains its header and no rows.
Keep participant responses in a separate file. Use pseudonymous participant
IDs. Follow the applicable consent and research review process before enrolling
people, and explain that participants may stop or lower the volume at any time.

## Training and session procedure

Record programming years, recent programming frequency, musical training years,
active practice, familiarity with MIDI or sonification, self-reported hearing
or access needs, and prior exposure to this repository. Store extra background
fields outside the supplied response CSV if needed. Do not infer musical skill
from years alone. Use the same headphones, comfortable calibrated volume,
display, and room for all conditions where feasible; record deviations.

Explain SONATA's end-exclusive ranges, boolean conditions, and resource limits.
Give everyone the same mapping legend and a fixed guided practice period using
tasks outside the measured 30-stimulus catalog. Include a branch, a terminating
loop, and a bounded recursion error. Record training time and comprehension
errors. Practice must teach the interface without showing any scored task's
answer. The present kit does not establish that a particular training duration
is sufficient.

For each task, start the timer when source and the assigned evidence become
available. Ask whether the behavior matches the stated intent. Collect the
suspected line and a brief explanation for an abnormal response, response time,
and confidence from 0 to 100. Permit replay in audio conditions and log replay
counts separately. Do not allow source edits, execution of modified source,
other task folders, or other representations during a scored trial. Take a
short break between blocks. An experimenter records actual responses; the
generated HTML does not silently collect them.

Use a predeclared task timeout, such as three minutes, consistently. Record a
timeout in `notes`; retain its elapsed time and unanswered status in the raw
record. The supplied summary script requires a binary decision, so exclude
unanswered rows from that input and report their counts separately. Never turn
missing answers into invented correct or incorrect responses.

## Workload and learning

Collect the six workload dimensions with consistent 0–100 anchors: mental,
physical, and temporal demand, performance, effort, and frustration. Orient the
performance field so 100 represents poor performance and 0 represents success.
The summary reports their **unweighted mean**, labeled `mean_raw_tlx`. This is
a Raw TLX adaptation; it does not implement the original paired-comparison
weights. Review NASA's official instructions before administration and document
the selected adaptation. [NASA Task Load Index](https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/).

The CSV supports workload after each trial; use that schedule consistently or
leave all six ratings blank for trials where no questionnaire was collected.
Do not copy a block rating onto five trials and count it as five observations.
If using one workload questionnaire per block, analyze those ratings separately.
The script accepts either all six ratings or none for a row.

Use accuracy and time changes across early and late trials as descriptive
learning measures. The script reports each participant's last-three minus
first-three differences when at least six observations exist. These measures
are confounded by task and condition order; they are not estimates of learning
caused by audio. Retention after a delay requires a further session.

## Optional blind listening exercise

The generator copies the built sum and off-by-one recordings into
`participant/blind_pair` using coded labels and puts their mapping and hashes
in `researcher_only/blind_pair_key.json`. If demo audio is absent, the manifest
reports fewer than two clips; do not run the exercise until both exist.

This pair is supplementary and follows the 15 main tasks. Give the intended
five-addition behavior and the same mapping training to every listener, play
the clips in randomized order, and ask which differs and why. Hide source,
timeline, duration labels where practical, and the key. Record actual order,
answer, confidence, replay count, and rationale in a separate dataset. Clip
duration itself can be a cue; this pair alone cannot show that listeners decoded
loop structure. Additional matched-length controls and unseen programs are
needed before making that stronger claim.

## Analysis plan

Copy the empty schema to a working response file. An experimenter fills each
row from actual observation and merges `expected_abnormal` from the private
key. A participant must not see that answer field during data collection.

```sh
.venv/bin/python scripts/study.py analyze observed.csv --output observed-summary.json
```

The script validates labels, finite numeric values, confidence/workload ranges,
and duplicate participant/trial pairs. Trial numbers are normalized to integers
before checking duplicates, so `1` and `1.0` identify the same trial. It reports observed counts, accuracy,
false-positive rates with normal-task denominators, false-negative rates with
abnormal-task denominators, median time, mean confidence, and Raw TLX where
available. Empty input produces zero observations and no condition statistics.
Missing denominators are represented as `null`.

Report exclusions and missingness before comparing conditions. Check the
private assignment key, balance, and timing logs. Inspect participant-level
differences and task-family results before aggregate means. Model repeated
observations within participants if fitting inferential models; do not treat
90 assigned trials as 90 independent people. Programming and musical experience
should enter a prespecified descriptive stratification or interaction analysis,
with uncertainty and small subgroup sizes reported. The supplied script does
not fit such a model or produce p-values. A causal claim needs a sound design,
completed observations, and an analysis that addresses order and task effects.
