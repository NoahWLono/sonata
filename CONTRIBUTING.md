# Contributing

Start with the tutorial and SPEC.md, then run `bash scripts/build.sh`. For the
short development cycle, activate the environment and run `python -m pytest -q`.
Node.js enables the browser state regression test; actual browser checks remain
necessary for playback, keyboard behavior, and layout changes.

A language change needs parser, runtime, reference-evaluator, canonical printing,
and musical round-trip coverage. Preserve SC1 compatibility or introduce an
explicit format version. Add a small failing example before fixing a bug.

A sonification change needs a documented listening meaning, deterministic tests,
trace/source provenance, and MIDI/WAV checks. Preserve original event IDs when
filtering. Keep generated recordings synchronized with source and configuration.
Use `python scripts/sync_examples.py` after editing repository examples so installed
packages receive the same material.

Report failures with the SONATA/Python versions, operating system, minimal source,
input fixtures, listening profile, and the relevant error or trace. Remove private
information before posting. Explain whether you tested the file format, a virtual
port, a physical MIDI device, or an actual DAW; these are different observations.

Proposals for new language features should include a concrete program that needs
them. Research contributions should separate automated measurements from human
results, provide study materials, and never invent participant data. Original
code and music contributions use the repository's MIT license. Identify licenses
and attribution for any third-party material before including it.
