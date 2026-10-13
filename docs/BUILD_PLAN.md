# SONATA implementation record

Goal: execute real programs, encode their syntax in audible MIDI notes, and render their behavior as linked musical events.

The user supplied the full research brief and explicitly requested autonomous implementation. Python keeps the reference semantics inspectable. Mido provides standard MIDI serialization and NumPy supports original synthesis. The browser interface uses a local HTTP server and Web Audio.

1. Acceptance gate: parse and run sum 1 through 5, record trace and notes, export WAV and MIDI, and prove the off-by-one version changes both result and musical structure. Tests live in `tests/test_milestone.py`.
2. Language: strict integer and boolean values, lexical blocks, bounded integer arrays, loops, functions, recursion, and explicit resource errors. Specify syntax and operational rules in `SPEC.md`.
3. Musical source: encode canonical source tokens as quantized note cells; reject malformed code scores; verify canonical AST and behavior after MIDI import. Preserve computational content in note events rather than metadata.
4. Debugger: editable source, bounded execution, trace stepping and breakpoints, state and stack inspection, linked source/timeline selection, synchronized audio, speed and export controls.
5. Validation: implement a separate evaluator; compare outputs, event linkage, note serialization, source round trips and WAV energy; add seeded generated programs and corrupt-input tests.
6. Experiments: record five demonstrations; measure mapping collisions and timing; produce a reproducible, counterbalanced study kit with no participant results invented.
7. Delivery: regenerate artifacts, run all tests, review the implementation, verify the browser, and commit a reproducible local repository.

Review focus: negative division, boolean/integer confusion, array aliasing and bounds, recursive resource exhaustion, malformed MIDI, stale debugger state, and claims that exceed automated evidence.
