# MIDI, instruments, and DAWs

SONATA can export MIDI files, separate voices into stems, and send or capture
messages through an optional native MIDI backend. File export and synthesized
WAV playback work without MIDI hardware, a DAW, or a soundfont.

## Choose the right MIDI representation

| File | Contents | Typical use |
| --- | --- | --- |
| Executable score from `sonata compile` | Quantized notes encoding SONATA tokens, including a checksum | Decode, inspect, or execute the musical source |
| Execution MIDI from `sonata listen --midi` | Notes derived from one program run | Listen, arrange, or inspect runtime behavior |
| Ordinary MIDI from another application | Its own notes and controls | Play through a port; it does not automatically become a SONATA program |

Changing an execution MIDI file changes a performance. It does not edit the
program. Changing an executable score must preserve its grammar and checksum;
use the debugger's token-score editor to make a validated program edit.

## Export a run and import it into a DAW

From an installed checkout:

```sh
sonata listen examples/sum.son --wav sum.wav --midi sum.mid --semantic
sonata listen examples/fibonacci.son --wav fibonacci.wav --stems fibonacci-parts
```

1. Create a DAW session at 120 BPM, the default export tempo.
2. Import `sum.mid` as MIDI tracks and preserve its timing and channels.
3. Assign a software instrument to each imported voice. MIDI carries note and
   instrument-selection messages. A receiving instrument synthesizes sound.
4. Import `sum.wav` at the session origin to hear SONATA's own rendering.
5. For individual parts, import the WAV or MIDI files named in
   `fibonacci-parts/manifest.json`. Every part keeps its original start time.

The standalone composition library also records instrument choices in its
manifest and MIDI program changes. A DAW or instrument may override program
changes. The three built-in WAV palettes synthesize their own timbres; they do
not reproduce every General MIDI instrument.

This is a format-level workflow. Automated tests check note timing, programs,
channels, files, and audio energy. No physical device or particular DAW has been
used to certify this release's live integration. A native RtMidi test on Linux
successfully sent and captured three notes through a temporary software port,
then replayed their input fixtures with the same program result. See the
[test record](verification/midi-loopback.json) and repeat it with
`python scripts/verify_midi_loopback.py` after installing the MIDI extra.

## Optional live ports

Install the extra in the same environment as SONATA:

```sh
python -m pip install 'sonata-lang[midi]'
sonata midi ports
sonata midi play sum.mid --port 'Your output port'
sonata midi record captured.json --port 'Your input port' --seconds 10
sonata midi replay captured.json --port 'Your output port' --speed 0.5
sonata midi inputs captured.json --output inputs.json
```

For a source checkout, `python -m pip install -e '.[midi]'` installs the extra.
The actual names come from `sonata midi ports`; the example names above are
placeholders. Configure a physical or virtual MIDI destination through your
operating system and DAW first. SONATA opens the explicitly selected port and
uses the RtMidi backend. Availability depends on the installed drivers and
native backend.

Playback preserves a MIDI file's tempo changes and schedules messages against a
monotonic clock. On completion, cancellation, or an exception, it attempts both
controller reset and all-sounds-off before closing a port it opened. An already
disconnected device may be unable to receive those messages. In Python, a
caller-supplied port stays open. The `stop` callback permits cooperative
cancellation during waits.

Mido provides the underlying port and reset/panic operations. See its
[port documentation](https://mido.readthedocs.io/en/stable/ports/index.html).

## Capture and replay contract

A recording contains integer microsecond timestamps and standard channel
messages:

```json
{
  "schema": "sonata-midi-recording",
  "version": 1,
  "duration_us": 500000,
  "messages": [
    {"time_us": 0, "message": {"type": "note_on", "channel": 0, "note": 60, "velocity": 90}},
    {"time_us": 500000, "message": {"type": "note_off", "channel": 0, "note": 60, "velocity": 0}}
  ]
}
```

The validator requires nondecreasing timestamps within the declared duration.
Limits are 100,000 received messages and 300 seconds per capture or file.
Replay speed is 0.1 through 10. Note, controller, program, pressure, and pitch
bend messages are supported. Capture counts and ignores SysEx and other system
messages; replay rejects them. A stream with too many ignored messages also
reaches the receive budget.

The recorded stream gives reproducible message content, order, and scheduled
relative times. An operating system, device, and synthesizer add timing jitter;
SONATA does not claim sample-accurate live delivery. Capture timestamps reflect
when the polling receiver observes a message, at approximately 2 ms polling
intervals. A missing note-off in a short recording is handled by the final reset.

`sonata midi inputs` converts positive-velocity note-on messages into three
integer-array inputs: pitches at index 0, velocities at index 1, and capture
timestamps in microseconds at index 2. It ignores other messages, including
zero-velocity note-on messages. The default limit is 256 sounding notes;
`--max-notes` can choose up to 4096. Overflow raises an error instead of dropping
notes. Programs consume these arrays through `input(index)`; the interpreter's
array limit must also accommodate them. The original recording preserves the
other channels and controls. See [embedding](EMBEDDING.md) for a runnable example.

## Reproduce without a device

```sh
python examples/integrations/replay_simulation.py
python examples/integrations/compose.py artifacts/composition
```

The first example uses an injected clock and output port, checking exact message
order and cleanup. The second exports an original composition, its three parts,
and a manifest. Neither command opens hardware.

## Music library

`sonata.musiclib` supplies `scale`, `chord`, `rhythm`, `Score`, and `export_stems`.
Times are quarter-note beats. `Score` preserves `Fraction` values until export
and accepts rational strings such as `"1/3"` for triplets.

```python
from sonata.musiclib import Score, chord

score = Score(bpm=108, palette="classical")
score.add_voice("piano", channel=0, program=0)
score.add_voice("strings", channel=1, program=48)
score.pattern("piano", [60, 62, 64], ["1/3"] * 3)
for pitch in chord(48, "minor"):
    score.note("strings", pitch, start=0, duration=2, velocity=70)
score.export("composition")
```

Each named voice has one distinct MIDI channel. Programs use MIDI's zero-based
0..127 numbering. Automatic channel allocation skips percussion channel 10
(index 9); explicitly choosing it is allowed. Presets include major, minor,
Dorian, pentatonic, and chromatic scales; chord qualities are `major`, `minor`,
`diminished`, `sus4`, `dominant7`, and `major7`.

The exact scheduling grid is 30,720 ticks per beat. A duration such as `1/7`
cannot be represented exactly on that grid, so the library rejects it. Export
also rejects overlapping unisons on one channel. Give independent unison parts
different channels or shorten their gates. Scores are limited to 100,000 notes
and 8,192 beats; the audio renderer imposes its tighter duration and synthesis
work limits. See [embedding](EMBEDDING.md) for execution-derived notes and
selective listening.
