"""Behavioral tests for runtime sonification and real export formats."""

import importlib
import wave

import numpy as np
import pytest


def event(index, kind="assign", value=0, depth=0, **data):
    return {
        "id": index, "kind": kind, "line": index + 1, "col": 1,
        "depth": depth, "function": "main", "stack": ["main"],
        "variables": {"x": value}, "data": {"value": value, **data},
    }


def module(name):
    try:
        return importlib.import_module(f"sonata.{name}")
    except ModuleNotFoundError:
        pytest.fail(f"The {name} runtime module has not been implemented")


def test_every_trace_event_has_deterministic_linked_notes():
    music = module("music")
    trace = [event(0, "declare", 1), event(1, value=[1, 3, 5]),
             event(2, "branch", True, taken=True), event(3, "call", depth=1),
             event(4, "error", "division by zero")]
    notes = music.sonify(trace)
    assert notes == music.sonify(trace)
    assert {note["event_id"] for note in notes} == set(range(5))
    assert [note["id"] for note in notes] == list(range(len(notes)))
    for note in notes:
        assert note["line"] == trace[note["event_id"]]["line"]
        assert note["start"] >= note["event_id"] * 0.25
        assert note["start"] < (note["event_id"] + 1) * 0.25
        assert 0 <= note["pitch"] <= 127
        assert 1 <= note["velocity"] <= 127
        assert note["duration"] > 0
    assert len([n for n in notes if n["event_id"] == 1]) >= 3
    assert len({n["voice"] for n in notes}) >= 2


def test_palettes_change_music_but_preserve_event_coverage():
    music = module("music")
    trace = [event(0, value=2), event(1, "return", 5)]
    variants = [music.sonify(trace, palette=p) for p in ("classical", "electronic", "ambient")]
    assert all({n["event_id"] for n in notes} == {0, 1} for notes in variants)
    assert variants[0] != variants[1] != variants[2]
    with pytest.raises(ValueError, match="palette"):
        music.sonify(trace, palette="missing")


def test_wav_is_audible_and_has_expected_timing(tmp_path):
    audio = module("audio")
    notes = [{"pitch": 69, "start": 0.5, "duration": 1.0, "velocity": 96, "channel": 0}]
    path = tmp_path / "tone.wav"
    stats = audio.render_wav(notes, path, bpm=120, sample_rate=22050)
    with wave.open(str(path)) as wav:
        assert wav.getframerate() == 22050
        assert wav.getsampwidth() == 2
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        assert wav.getnframes() / 22050 == pytest.approx(0.95, abs=1 / 22050)
    assert stats["duration"] == pytest.approx(0.95, abs=1 / 22050)
    assert stats["rms"] > 0.01
    assert np.max(np.abs(samples)) > 1000
    assert np.max(np.abs(samples[:5000])) == 0


def test_midi_roundtrip_preserves_pitches_timing_channels_and_velocity(tmp_path):
    midi = module("midi")
    notes = [
        {"pitch": 0, "start": 0.0, "duration": 0.25, "velocity": 1, "channel": 0},
        {"pitch": 127, "start": 0.25, "duration": 1.0, "velocity": 127, "channel": 15},
        {"pitch": 64, "start": 0.5, "duration": 0.75, "velocity": 82, "channel": 2},
    ]
    path = tmp_path / "notes.mid"
    midi.write_midi(notes, path, bpm=123)
    assert path.read_bytes().startswith(b"MThd")
    restored = midi.read_midi(path)
    fields = ("pitch", "start", "duration", "velocity", "channel")
    assert [tuple(n[k] for k in fields) for n in restored] == [tuple(n[k] for k in fields) for n in notes]


@pytest.mark.parametrize("palette", ["classical", "electronic", "ambient"])
def test_palette_audio_is_deterministic(tmp_path, palette):
    audio = module("audio")
    notes = [{"pitch": 60, "start": 0, "duration": 0.25, "velocity": 90, "channel": 0}]
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    audio.render_wav(notes, a, palette=palette)
    audio.render_wav(notes, b, palette=palette)
    assert a.read_bytes() == b.read_bytes()


def test_audio_rejects_unsafe_duration_without_creating_output(tmp_path):
    audio = module("audio")
    path = tmp_path / "too-long.wav"
    notes = [{"pitch": 60, "start": 1e9, "duration": 1, "velocity": 90, "channel": 0}]
    with pytest.raises(ValueError, match="duration|limit"):
        audio.render_wav(notes, path)
    assert not path.exists()


def test_audio_rejects_excessive_polyphonic_work_before_synthesis(tmp_path, monkeypatch):
    audio = module("audio")
    def unexpected_synthesis(*args):
        pytest.fail("render began synthesizing before checking its work budget")
    monkeypatch.setattr(audio, "_tone", unexpected_synthesis)
    notes = [{"pitch": 60, "start": 0, "duration": 500, "velocity": 90}] * 100
    with pytest.raises(ValueError, match="work|budget|limit"):
        audio.render_wav(notes, tmp_path / "oversized.wav")


@pytest.mark.parametrize("field,value", [("pitch", 128), ("velocity", 0), ("channel", 16),
                                         ("start", -1), ("start", float("nan")),
                                         ("duration", 0), ("duration", float("inf"))])
def test_exporters_reject_malformed_notes_without_output(tmp_path, field, value):
    audio, midi = module("audio"), module("midi")
    note = {"pitch": 60, "start": 0, "duration": 1, "velocity": 90, "channel": 0, field: value}
    for writer, suffix in [(audio.render_wav, "wav"), (midi.write_midi, "mid")]:
        path = tmp_path / f"invalid.{suffix}"
        with pytest.raises(ValueError):
            writer([note], path)
        assert not path.exists()


def test_palette_waveforms_are_distinct(tmp_path):
    audio = module("audio")
    note = {"pitch": 60, "start": 0, "duration": 1, "velocity": 90}
    waveforms = []
    for palette in ("classical", "electronic", "ambient"):
        path = tmp_path / f"{palette}.wav"
        audio.render_wav([note], path, palette=palette)
        waveforms.append(path.read_bytes())
    assert len(set(waveforms)) == 3


def test_wav_rejects_inaudible_high_notes_at_low_sample_rate(tmp_path):
    audio = module("audio")
    note = {"pitch": 127, "start": 0, "duration": 1, "velocity": 90}
    with pytest.raises(ValueError, match="sample_rate|Nyquist"):
        audio.render_wav([note], tmp_path / "inaudible.wav", sample_rate=8000)


def test_function_motif_follows_name_across_call_sites():
    music = module("music")
    first = event(0, "call", name="factorial")
    second = event(1, "call", name="factorial")
    first["line"], second["line"] = 3, 9
    notes = music.sonify([first, second])
    first_motif = [n["pitch"] for n in notes if n["event_id"] == 0]
    second_motif = [n["pitch"] for n in notes if n["event_id"] == 1]
    assert first_motif == second_motif
    assert {n["line"] for n in notes} == {3, 9}
    third = event(0, "call", name="binary_search")
    third["line"] = 3
    assert [n["pitch"] for n in music.sonify([third])] != first_motif


def test_audio_accepts_symbolic_voice_names(tmp_path):
    audio = module("audio")
    notes = [{"pitch": 60, "start": 0, "duration": 0.25, "velocity": 90,
              "channel": 1, "voice": "code"}]
    assert audio.render_wav(notes, tmp_path / "code.wav")["rms"] > 0.01


@pytest.mark.parametrize("palette", ["classical", "electronic", "ambient"])
def test_repeated_array_pitches_roundtrip_with_exact_note_intervals(tmp_path, palette):
    from sonata.language import parse
    from sonata.runtime import execute
    music, midi = module("music"), module("midi")
    notes = music.sonify(execute(parse("return [0,0];"))["trace"], palette=palette)
    path = tmp_path / f"array-{palette}.mid"
    midi.write_midi(notes, path, palette=palette)
    symbolic = lambda score: sorted((n["pitch"], n["channel"], round(n["start"] * 480),
                                    round(n["duration"] * 480)) for n in score)
    assert symbolic(midi.read_midi(path)) == symbolic(notes)


def test_generic_midi_rejects_ambiguous_same_key_overlap(tmp_path):
    midi = module("midi")
    notes = [{"pitch": 60, "channel": 0, "velocity": 90, "start": 0, "duration": 2},
             {"pitch": 60, "channel": 0, "velocity": 80, "start": 1, "duration": 0.5}]
    path = tmp_path / "ambiguous.mid"
    with pytest.raises(ValueError, match="overlap|ambiguous"):
        midi.write_midi(notes, path)
    assert not path.exists()
