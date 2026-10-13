# Release and compatibility policy

SONATA 1.0.0 stabilizes the documented language and its SC1 source codec. The
release designation describes the software contract. It does not establish a
human debugging benefit or universal device compatibility.

## Versioned interfaces

- Source syntax and semantics: SPEC.md, including integer/array/resource bounds.
- SC1 executable MIDI: existing operation pitches and operand encoding remain
  unchanged. V1 keywords use the existing identifier melodies. Prototype
  programs using newly reserved words or builtin function names need renaming.
- Execution traces: the event shape in SPEC.md is the reference contract. New
  optional fields may be added; existing field meanings will not silently change.
- Listening profiles: version 1. Omitted profile means the original line-based
  mapping; an explicit object selects semantic mapping unless configured otherwise.
- Recorded MIDI: `sonata-midi-recording`, version 1, integer microsecond timestamps.
- Python adapter: `sonata-python-trace`, version 1. It observes trusted synchronous
  CPython code and is not an execution sandbox.

Semantic version changes apply to documented APIs. Private names beginning with
an underscore are implementation details. Future incompatible language, codec,
or schema changes require a major version or an explicit new format identifier.
Existing encoded scores must never silently execute with different meanings.

Runtime audio intentionally compresses information. Different computations may
share a phrase. Keep trace/state views available and preserve profile settings
with exported results. Wall-clock timeouts, input capture jitter, and hardware
scheduling are not deterministic. Recorded timestamp streams, instruction/depth
bounds, and the symbolic score are reproducible. PCM byte identity is checked
within the pinned environment; cross-platform floating-point byte identity is
not promised.

## Complete local build

On a system with Python 3.12+ and a POSIX shell:

```sh
bash scripts/build.sh
```

Node.js runs the browser state regression harness. The browser itself runs
without Node. FFmpeg and fontconfig enable optional video generation. Their
absence does not prevent language, MIDI, WAV, or debugger operation.

For Windows or separate development steps, create and activate a virtual
environment, then use:

```sh
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
python scripts/sync_examples.py --check
python -m pytest -q
python scripts/build.py
python scripts/v1_demos.py
python experiments/analyze.py --root .
python scripts/study.py generate --root .
python scripts/check_artifacts.py
```

The GitHub Actions matrix runs Python 3.12 and 3.14 on Linux, Windows, and macOS.
Saved release evidence distinguishes local tests from completed remote jobs.

## Distribution verification

```sh
python -m pip install -r requirements-build.txt
python -m build --no-isolation
python scripts/package_smoke.py dist/sonata_lang-1.0.0-py3-none-any.whl dist/sonata_lang-1.0.0.tar.gz --report docs/verification/package-smoke.json
```

The smoke test installs each archive into a fresh environment and works outside
the checkout. It exercises copied examples, fixtures, modules, audio generation,
MIDI round trips, independent verification, and packaged debugger resources.
A network connection is needed to obtain dependencies unless they are cached.

Before publishing, run the full tests and artifact verification, inspect the
Git diff, resolve review findings, scan tracked content for credentials/private
paths, and record exact artifact hashes. Create the public repository only after
these checks pass. Push the verified commit and `v1.0.0` tag, attach wheel/sdist
and their checksum file to the GitHub release, and confirm the remote tag and
downloaded asset hashes. Do not overwrite a published release tag to hide a fix;
release a patch version with its own verification instead.

## Scope boundaries

The local debugger is a development tool bound to loopback with host/origin
checks. It is not a multi-user internet service. SONATA programs cannot access
host Python, files, networks, random state, or wall-clock values. Local imports
resolve only named sibling source modules selected through the CLI.

The optional Python trace adapter executes trusted host code with ordinary host
permissions. Its tracing limits bound observations and traced Python execution;
they cannot interrupt blocking native code or control other threads. MIDI port
availability and operating-system audio routing vary. The release includes
in-memory timing tests and a successful native RtMidi test through a temporary
software port on Linux. No physical instrument or DAW was tested. To repeat the
optional software-port check with the MIDI extra installed, run
`python scripts/verify_midi_loopback.py`.
