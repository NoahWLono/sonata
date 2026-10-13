# Local SONATA song conversions

These scores were converted from user-supplied MIDI files. The repository includes their SONATA source, input fixtures, reconstructed MIDI, rendered WAV, and verification reports. Playback runs locally. See [media attribution](MEDIA_NOTICE.md) for the scope of the project license.

| SONATA score | Notes | MIDI duration | Arrangement |
| --- | ---: | ---: | --- |
| [Megalovania.son](Megalovania.son) | 4,705 | 2:36.000 | 9 MIDI tracks, including percussion |
| [BADAPPLE.son](BADAPPLE.son) | 15,271 | 3:35.657 | 13 MIDI tracks, including percussion |
| [ACruelAngelsThesis.son](ACruelAngelsThesis.son) | 1,967 | 4:02.782 | Piano arrangement with tempo changes |

## Watch the songs in the SONATA debugger

From the repository root, start the debugger with the local song provider:

```sh
.venv/bin/python local-songs/debugger.py --port 8977
```

Open <http://127.0.0.1:8977/>, choose a title from **Local songs**, and press **Play**. The existing SONATA debugger displays the score source, piano roll, and event inspector while playing the rendered recording. Pause, rewind, speed changes, note selection, stepping, and line breakpoints let you inspect a passage.

The audio playhead drives the highlighted source line. A note points to the catalog `print` statement that defined its MIDI message. The inspector also identifies the input page, offset, and interpreter output event that scheduled it. SONATA executes the program before playback; the song timeline displays that resulting schedule. Piano-roll rectangles show MIDI key durations, while the recording also contains instrument release tails and effects.

Song source is read-only in this view. The current source, fixture, MIDI, and WAV must match their verification reports before playback is accepted. Choose a normal example to return to source editing and the ordinary execution debugger. Local songs are available only through this launcher; ordinary `sonata debug` starts without access to this folder.

## Listen without the debugger

Open `index.html` in a browser, or open any of the three WAV files in your music player. The WAV files were synthesized from MIDI reconstructed by executing the SONATA scores. Their timbres come from FluidR3 GM, so they reflect the supplied MIDI arrangements rather than the original commercial recordings. Each WAV has a short release tail after the MIDI ends.

To serve the listening page locally, run this from the repository root:

```sh
python3 -m http.server 8978 --bind 127.0.0.1 --directory local-songs
```

Then open <http://127.0.0.1:8978/>.

## Execute a score

Keep each `.son` file with its matching `.inputs.json`. The source contains the message catalog and the program that emits the performance. The companion file contains the event sequence and timing, divided into bounded input arrays. Both files are editable.

From the repository root:

```sh
.venv/bin/python local-songs/score_bridge.py perform local-songs/Megalovania.son
.venv/bin/python local-songs/render_audio.py local-songs/Megalovania.mid
```

Replace `Megalovania` with `BADAPPLE` or `ACruelAngelsThesis` to rebuild the others. The first command runs SONATA and the independent reference evaluator, compares their output, and writes the performance MIDI. The second creates its WAV using FluidSynth and the separately downloaded SoundFont. Reload the listening page after a render.

The supplied piano arrangement is quieter than the other two files. To reproduce its delivered recording's volume, add `--gain 0.8` to its render command. Megalovania and Bad Apple use the default gain of `0.2`.

Use this bridge for song playback. The standard `sonata listen` command sonifies runtime debugging events; it does not interpret the score's printed MIDI protocol.

## How the conversion works

The unchanged SONATA v1 interpreter executes the score. Every distinct MIDI message appears as a `print([...])` catalog entry with a readable comment. A note-on entry includes the channel, pitch, and velocity; other entries carry instruments, controllers, tempo, or track metadata. Editing a catalog entry changes every occurrence of that message in the performance.

Each integer in the companion input file is `delta_ticks * 65536 + catalog_index`. The SONATA program reads and prints each page, checks the per-track event counts, and returns the total count. The bridge consumes only the program's actual output to reconstruct MIDI. It does not reopen the original download during playback. Notes remain in their original tracks and order, including simultaneous messages, overlapping notes, zero-velocity note-offs, and end-of-track timing.

The fixture data is necessary for these conversions: placing all of Bad Apple's events directly in source would exceed v1's syntax bounds. This local performance protocol uses existing SONATA output and input fixtures. The language implementation is unchanged.

## Verification and reproducibility

The three `.verification.json` files record source, fixture, original MIDI, and reconstructed MIDI hashes. Conversion checks every message and tick delta in every track, along with MIDI type and PPQ. MIDI byte layout can change during serialization, while the parsed events stay equal.

The reference evaluator independently checks execution semantics but shares the parser with the main interpreter. Both MIDI paths use `mido`, so that dependency is shared too. The audio reports measure duration, peak, RMS, and clipped samples. They do not assess musical recognition by a human listener.

Run the focused local checks:

```sh
.venv/bin/python -m pytest -q local-songs/test_score_bridge.py local-songs/test_render_audio.py local-songs/test_debug_performances.py
```

To repeat a conversion from its supplied input:

```sh
.venv/bin/python local-songs/score_bridge.py convert \
  "$HOME/Downloads/Megalovania.mid" local-songs/Megalovania.son
.venv/bin/python local-songs/score_bridge.py convert \
  "$HOME/Downloads/badapple!!midifull.mid" local-songs/BADAPPLE.son
.venv/bin/python local-songs/score_bridge.py convert \
  "$HOME/Downloads/Evangelion - Cruel Angel's Thesis.mid" local-songs/ACruelAngelsThesis.son
```

These commands replace the generated score and fixture files, so save any musical edits first. The local renderer uses the existing virtual environment's `mido` and `numpy` packages, the installed `fluidsynth` executable, and `assets/FluidR3_GM.sf2`. Its license and download provenance are retained under `assets/`.

## SoundFont setup for rendering

Playing the included WAV recordings needs no SoundFont or FluidSynth installation. To rebuild recordings, install FluidSynth with your system package manager and place FluidR3 GM at `local-songs/assets/FluidR3_GM.sf2`. The SoundFont is 148 MB and is omitted from Git. Its MIT license is included in `assets/FluidR3-LICENSE.txt`.

On Linux, these commands download the pinned Debian package, verify it, and extract only the font. They require `curl`, `sha256sum`, `ar`, and `tar`. Run them from the repository root:

```sh
(
  set -eu
  package_dir=$(mktemp -d)
  trap 'rm -rf "$package_dir"' EXIT
  curl --fail --location --output "$package_dir/font.deb" \
    https://deb.debian.org/debian/pool/main/f/fluid-soundfont/fluid-soundfont-gm_3.1-6_all.deb
  printf '%s  %s\n' \
    9965fbcc6acee17d6f72b685d28c7f968ec64eba14645445b476d5c6cc2eee4c \
    "$package_dir/font.deb" | sha256sum --check
  ar p "$package_dir/font.deb" data.tar.xz | tar -xJOf - \
    ./usr/share/sounds/sf2/FluidR3_GM.sf2 > "$package_dir/FluidR3_GM.sf2"
  printf '%s  %s\n' \
    74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0 \
    "$package_dir/FluidR3_GM.sf2" | sha256sum --check
  mv "$package_dir/FluidR3_GM.sf2" local-songs/assets/FluidR3_GM.sf2
)
```

The JSON provenance file retains the upstream URL and hashes. Audio-report command paths have been made relative to the repository root for portability; the recorded media hashes are unchanged.
