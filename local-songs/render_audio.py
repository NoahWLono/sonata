#!/usr/bin/env python3
"""Offline GM rendering of local SONATA-reconstructed MIDI performances.

Usage: .venv/bin/python local-songs/render_audio.py local-songs/output/NAME.mid
Requires FluidSynth on PATH and the project's mido/numpy dependencies.
No MIDI input or real-time audio driver is opened. Nothing is uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave

import mido
import numpy as np


ASSETS = Path(__file__).resolve().parent / "assets"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_wav(path: Path) -> dict:
    """Stream PCM data and measure duration, peak, RMS, and clipped samples."""
    count = clipped = 0
    squares = peak = 0.0
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        rate = stream.getframerate()
        frames = stream.getnframes()
        if stream.getsampwidth() != 2 or stream.getcomptype() != "NONE":
            raise ValueError("expected uncompressed signed 16-bit PCM WAV")
        while raw := stream.readframes(65536):
            samples = np.frombuffer(raw, dtype="<i2")
            values = samples.astype(np.float64) / 32768
            peak = max(peak, float(np.abs(values).max(initial=0)))
            squares += float(np.dot(values, values))
            count += samples.size
            clipped += int(np.count_nonzero((samples == -32768) | (samples == 32767)))
    if count != frames * channels:
        raise ValueError("truncated WAV sample data")
    if squares == 0:
        raise ValueError("silent WAV")
    return {
        "sample_rate": rate,
        "channels": channels,
        "sample_width_bytes": 2,
        "frames": frames,
        "duration_seconds": frames / rate,
        "peak": peak,
        "rms": math.sqrt(squares / count),
        "clipped_samples": clipped,
        "sha256": digest(path),
    }


def render_command(midi: Path, wav: Path, font: Path, gain: float) -> list[str]:
    return [
        "fluidsynth", "-ni", "-q", "-F", str(wav),
        "-T", "wav", "-O", "s16", "-r", "44100", "-g", str(gain),
        "-o", "player.timing-source=sample",
        "-o", "synth.polyphony=1024",
        "-o", "synth.cpu-cores=1",
        "-o", "synth.lock-memory=0",
        "-o", "synth.reverb.active=1",
        "-o", "synth.reverb.room-size=0.35",
        "-o", "synth.reverb.level=0.25",
        "-o", "synth.chorus.active=1",
        str(font), str(midi),
    ]


def render(midi: Path, font: Path, gain: float = 0.2) -> dict:
    midi = midi.resolve(strict=True)
    font = font.resolve(strict=True)
    wav = midi.with_suffix(".wav")
    recording = mido.MidiFile(midi)
    if recording.type == 2:
        raise ValueError("independent type-2 patterns need explicit sequencing")
    expected_duration = recording.length
    if not 0 < expected_duration <= 900:
        raise ValueError("expected a positive MIDI duration of at most 15 minutes")
    for attempt in range(4):
        command = render_command(midi, wav, font, gain)
        process = subprocess.run(command, capture_output=True, text=True, timeout=600)
        wav.with_suffix(".render.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        process.check_returncode()
        report = inspect_wav(wav)
        if report["clipped_samples"] == 0 and report["peak"] < 0.99:
            break
        gain /= 2
    else:
        raise ValueError("render remains clipped after reducing synthesis gain")
    if not expected_duration - 0.1 <= report["duration_seconds"] <= expected_duration + 30:
        raise ValueError("render duration does not match the MIDI performance and tail")
    result = {
        "midi_file": midi.name,
        "midi_sha256": digest(midi),
        "midi_duration_seconds": expected_duration,
        "midi_tracks": len(recording.tracks),
        "positive_note_ons": sum(message.type == "note_on" and message.velocity > 0
                                 for track in recording.tracks for message in track),
        "soundfont": font.name,
        "soundfont_sha256": digest(font),
        "renderer": "FluidSynth",
        "gain": gain,
        "retries_for_clipping": attempt,
        "command": command,
        "wav_file": wav.name,
        "wav": report,
    }
    wav.with_suffix(".audio-report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi", nargs="+", type=Path)
    parser.add_argument("--font", type=Path, default=ASSETS / "FluidR3_GM.sf2")
    parser.add_argument("--gain", type=float, default=0.2)
    args = parser.parse_args()
    if not math.isfinite(args.gain) or not 0 < args.gain <= 1:
        parser.error("gain must be in (0, 1]")
    for midi in args.midi:
        result = render(midi, args.font, args.gain)
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
