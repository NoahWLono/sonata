"""Original deterministic additive/FM synthesis for SONATA's three palettes."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from .music import palette_config, validate_bpm, validated_notes


RELEASE_SECONDS = 0.2
MAX_DURATION_SECONDS = 300
MAX_FRAMES = 30_000_000
MAX_SYNTHESIS_FRAMES = 60_000_000


def _tone(pitch: int, duration: float, velocity: int, voice: int,
          sample_rate: int, palette: str) -> np.ndarray:
    frames = math.ceil((duration + RELEASE_SECONDS) * sample_rate)
    time = np.arange(frames, dtype=np.float64) / sample_rate
    frequency = 440.0 * 2 ** ((pitch - 69) / 12)
    phase = 2 * np.pi * frequency * time
    # Harmonics above Nyquist are omitted so high notes never fold downward.
    if frequency >= sample_rate / 2:
        signal = np.zeros(frames)
    elif palette == "classical":
        signal = np.zeros(frames)
        for harmonic in range(1, 7):
            if frequency * harmonic < sample_rate / 2:
                weight = (0.62 if voice % 2 else 0.46) ** (harmonic - 1)
                signal += weight * np.sin(phase * harmonic) * np.exp(-time * harmonic * 1.8)
    elif palette == "electronic":
        # A band-limited harmonic lead, with a slow resonant pulse envelope.
        signal = np.zeros(frames)
        for harmonic in range(1, 9):
            if frequency * harmonic < sample_rate / 2:
                signal += np.sin(phase * harmonic) / harmonic
        signal *= 0.8 + 0.2 * np.cos(2 * np.pi * 3 * time)
    else:
        signal = np.sin(phase)
        if frequency * 2 < sample_rate / 2:
            signal += 0.3 * np.sin(phase * 2 + 0.6 * np.sin(2 * np.pi * 0.7 * time))
        if frequency * 1.005 < sample_rate / 2:
            signal += 0.35 * np.sin(phase * 1.005)
    attack = min(duration / 3, 0.06 if palette == "ambient" else 0.008)
    envelope = np.minimum(time / max(attack, 1 / sample_rate), 1)
    release = np.clip(1 - np.maximum(time - duration, 0) / RELEASE_SECONDS, 0, 1)
    envelope *= release ** 2
    return (signal * envelope * (velocity / 127) * 0.23).astype(np.float32)


def render_wav(notes, path, bpm: float = 120, palette: str = "classical",
               sample_rate: int = 22050) -> dict:
    """Write mono 16-bit PCM, returning measured timing and normalized RMS.

    Reject excessive renders before allocating buffers or opening the output.
    The final release tail is exactly 0.2 seconds (within one sample).
    """
    palette_config(palette)
    tempo = validate_bpm(bpm)
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or not 8000 <= sample_rate <= 96000:
        raise ValueError("sample_rate must be an integer between 8000 and 96000")
    score = validated_notes(notes)
    seconds_per_beat = 60 / tempo
    end = max((n["start"] + n["duration"] for n in score), default=0) * seconds_per_beat
    duration = end + RELEASE_SECONDS
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(f"Audio duration limit exceeded ({MAX_DURATION_SECONDS} seconds)")
    frames = math.ceil(duration * sample_rate)
    if frames > MAX_FRAMES:
        raise ValueError(f"Audio frame limit exceeded ({MAX_FRAMES})")
    work = sum(math.ceil((note["duration"] * seconds_per_beat + RELEASE_SECONDS) * sample_rate)
               for note in score)
    if work > MAX_SYNTHESIS_FRAMES:
        raise ValueError(f"Audio synthesis work limit exceeded ({MAX_SYNTHESIS_FRAMES} note frames)")
    if any(440 * 2 ** ((note["pitch"] - 69) / 12) >= sample_rate / 2 for note in score):
        raise ValueError("A note exceeds the Nyquist limit; increase sample_rate to render that pitch")
    signal = np.zeros(frames, dtype=np.float32)
    for note in score:
        start = round(note["start"] * seconds_per_beat * sample_rate)
        voice = note.get("voice", note["channel"])
        if not isinstance(voice, int):
            voice = note["channel"]
        tone = _tone(note["pitch"], note["duration"] * seconds_per_beat,
                     note["velocity"], voice,
                     sample_rate, palette)
        # Rounding onset and tail independently can differ by one sample.
        count = min(len(tone), frames - start)
        signal[start:start + count] += tone[:count]
    peak = float(np.max(np.abs(signal))) if frames else 0
    if peak > 0.95:
        signal *= 0.95 / peak
    rms = float(np.sqrt(np.mean(np.square(signal, dtype=np.float64))))
    pcm = np.rint(signal * 32767).astype("<i2")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())
    return {"duration": frames / sample_rate, "frames": frames,
            "sample_rate": sample_rate, "rms": rms}
