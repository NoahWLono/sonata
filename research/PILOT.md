# Small usability pilot

The purpose of this pilot is to find confusing controls and learn which musical
cues participants can interpret. It is preparation for the controlled experiment
in PROTOCOL.md. A small convenience sample cannot establish a general debugging
benefit. No participants have been enrolled or data collected in this repository.

## Session, approximately 25 minutes

Invite programmers with a range of musical experience. Record years of
programming, familiarity with the example algorithms, musical training, and any
hearing/access preferences they choose to disclose. Use anonymous participant
codes. Explain that participation is voluntary, they may stop or skip a task,
and the software rather than the participant is being evaluated. Follow the
institution's applicable consent/review procedure before research recruitment.

Give a five-minute demonstration of source, trace, and runtime music. Explain
branches, calls/returns, errors, and finite pitch ranges. Let the participant
choose comfortable volume and playback speed. Use the same palette/profile for
compared examples, and record any setting changes.

Ask the participant to:

1. Run the sum example, locate the returned value, and select an audible event.
2. Compare the correct and defective loops. Describe the difference, identify
   its source location, and state confidence before seeing the answer.
3. Listen to Fibonacci and explain what changes with recursion depth.
4. Filter the sorting example to array updates and inspect a muted event.
5. Change a number in the executable musical score, validate it, export MIDI,
   and explain what that score encodes.

Alternate the order of tasks 2 and 3 across participants. Do not coach during a
measured task; record a help request and provide assistance only after the
participant chooses to stop. Note where a participant looks, what they expect,
where they become stuck, and whether sound changes their explanation. Do not
record screens, voices, or identifying information without explicit consent.

## Record observations without inventing them

Use the existing empty study response template for scored study trials. For
this exploratory pilot, create one row per task in a separate CSV with fields:
`participant,task,order,completed,correct,elapsed_seconds,confidence_1_5,
help_requested,programming_years,musical_training_years,settings,observation`.
An absent observation stays missing. Do not enter generated or agent responses
as human observations. Distinguish an incorrect answer from an unfinished task.

Ask afterward which sounds they remembered, which were distracting, what exact
information they still needed to read, and whether they would use the tool for
learning, debugging, or composition. Ask for workload with the study's raw
NASA-TLX procedure if appropriate; do not reinterpret confidence as workload.

Summarize counts, timing distributions, help requests, and concrete usability
problems. Preserve contradictory observations. Treat causal claims about sound
as hypotheses for the randomized A/B/C study. Use the controlled kit's analysis
script only for data meeting its schema; exploratory pilot notes are not an
additional experimental condition.

## Decisions the pilot can inform

- Whether the initial listening vocabulary needs fewer cues or clearer lessons.
- Whether selective listening and comparison help participants form an accurate
  account of a particular execution.
- Whether educational examples, musical composition, or trace adapters deserve
  the next development effort.
- Which keyboard, screen-reader, timing, or audio adjustments need co-design.

Automated signal tests demonstrate measurable differences and symbolic recovery.
They cannot answer these usability questions on participants' behalf.
