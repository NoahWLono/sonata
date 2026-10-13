"""Local tests for the offline playback artifact validator."""
from pathlib import Path
import importlib.util
import wave

import numpy as np
import pytest


def helper():
    path = Path(__file__).with_name("render_audio.py")
    assert path.exists(), "render_audio.py has not been implemented"
    spec = importlib.util.spec_from_file_location("local_render_audio", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_wave(path, samples):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(44100)
        stream.writeframes(np.asarray(samples, dtype="<i2").tobytes())


def test_wave_validator_counts_duration_energy_and_clipped_samples(tmp_path):
    path = tmp_path / "tone.wav"
    samples = np.zeros((44100, 2), dtype="<i2")
    samples[10] = (16384, -16384)
    samples[20] = (32767, -32768)
    write_wave(path, samples)
    report = helper().inspect_wav(path)
    assert report["duration_seconds"] == 1
    assert report["channels"] == 2
    assert report["sample_rate"] == 44100
    assert report["peak"] == 1
    assert report["rms"] > 0
    assert report["clipped_samples"] == 2


def test_wave_validator_rejects_silence(tmp_path):
    path = tmp_path / "silence.wav"
    write_wave(path, np.zeros((44100, 2), dtype="<i2"))
    with pytest.raises(ValueError, match="silent"):
        helper().inspect_wav(path)


def test_render_uses_offline_audio_and_bounded_settings():
    command = helper().render_command(Path("score.mid"), Path("score.wav"), Path("font.sf2"), 0.2)
    assert command[:4] == ["fluidsynth", "-ni", "-q", "-F"]
    assert "player.timing-source=sample" in command
    assert "synth.polyphony=1024" in command
    assert "synth.cpu-cores=1" in command
    assert command[-2:] == ["font.sf2", "score.mid"]
