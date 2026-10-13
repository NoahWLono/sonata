# Dependencies and references

The checked build uses Python 3.14.8; the pinned NumPy release requires Python
3.12 or later. `requirements-lock.txt` records exact versions and
`pyproject.toml` records runtime and test dependencies.

| Component | Use | Upstream license |
| --- | --- | --- |
| Python | Interpreter host, local HTTP, WAV and JSON I/O | Python Software Foundation |
| NumPy | Original waveform synthesis and signal measurements | BSD-3-Clause |
| Mido | Standard MIDI file serialization | MIT |
| python-rtmidi, optional | Native live MIDI ports | MIT; embedded RtMidi carries its upstream notices |
| setuptools, build, wheel, pyproject-hooks | Release packaging | Upstream notices included in installed distributions |
| pytest | Test runner | MIT |
| Hypothesis | Deterministic generated test cases | MPL-2.0 |
| FFmpeg, optional system tool | Demo video encoding | Build-dependent LGPL/GPL; executable not bundled |

Transitive dependencies retain their upstream licenses and notices in their
installed distributions. SONATA's original source is MIT licensed. No
proprietary samples, soundfonts or fonts are bundled. The optional video uses
the host's monospace font.

Primary references:

- [Mido MIDI files](https://mido.readthedocs.io/en/1.2.10/midi_files.html): note events, ticks and tempo.
- [NASA Task Load Index](https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/): source for the proposed workload instrument. Using it does not establish workload improvement.

The source score's encoding and the runtime mapping are implemented here as
experimental designs. No claim is made that program sonification itself is
new, or that these mappings outperform earlier work.
