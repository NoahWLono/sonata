"""Projection tests use an original synthetic score, never song material."""
import hashlib
import json
from pathlib import Path
import sys
import wave

import mido
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import debug_performances as debug
from score_bridge import convert_midi, run_score


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def score(tmp_path, monkeypatch):
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage('set_tempo', tempo=500000),
        mido.MetaMessage('set_tempo', tempo=1000000, time=480),
        mido.MetaMessage('end_of_track', time=480),
    ]))
    midi.tracks.append(mido.MidiTrack([
        mido.Message('program_change', channel=1, program=81),
        mido.Message('note_on', channel=1, note=60, velocity=90),
        mido.Message('note_on', channel=1, note=60, velocity=100, time=240),
        mido.Message('pitchwheel', channel=1, pitch=1024),
        mido.Message('note_off', channel=1, note=60, time=240),
        mido.Message('note_on', channel=1, note=60, velocity=0, time=480),
        mido.Message('note_off', channel=1, note=60),  # harmless orphan
        mido.MetaMessage('end_of_track'),
    ]))
    midi.tracks.append(mido.MidiTrack([
        mido.Message('note_on', channel=9, note=36, velocity=90),
        mido.Message('note_off', channel=9, note=36, time=960),
        mido.MetaMessage('end_of_track'),
    ]))
    original = tmp_path / 'input.mid'
    midi.save(original)
    source = tmp_path / 'Synthetic.son'
    convert_midi(original, source, page_size=3)
    _, result, report = run_score(source, source.with_suffix('.mid'))
    source.with_suffix('.verification.json').write_text(json.dumps(report))
    wav = source.with_suffix('.wav')
    with wave.open(str(wav), 'wb') as stream:
        stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\x01\x00' * 16000)
    source.with_suffix('.audio-report.json').write_text(json.dumps({
        'midi_sha256': digest(source.with_suffix('.mid')),
        'wav': {'sha256': digest(wav), 'duration_seconds': 2.0},
    }))
    monkeypatch.setattr(debug, 'SONGS', {'Synthetic': 'Synthetic arrangement'})
    return source, result


def test_projection_preserves_global_tempo_notes_and_exact_source_provenance(score):
    source, result = score
    provider = debug.LocalPerformances(source.parent)
    payload = provider.payload('Synthetic')
    assert payload['performance']['duration_seconds'] == 2
    assert payload['performance']['duration_beats'] == 4
    assert payload['performance']['trace_kind'] == 'scheduled_midi_projection'
    assert payload['result']['instructions'] == result['instructions']
    assert payload['result']['return_value'] == result['return_value']
    events = payload['result']['trace']
    assert len(events) == result['return_value']
    assert [(e['data']['absolute_tick'], e['data']['track'], e['data']['track_event']) for e in events] == sorted(
        (e['data']['absolute_tick'], e['data']['track'], e['data']['track_event']) for e in events)
    assert len(payload['notes']) == 3
    melodic = [n for n in payload['notes'] if n['channel'] == 1]
    assert [(n['start'], n['duration']) for n in melodic] == [(0, 1), (0.5, 2.5)]
    assert payload['performance']['orphan_note_offs'] == 1
    for event in events:
        catalog = result['trace'][event['data']['catalog_trace_id']]
        emission = result['trace'][event['data']['emission_trace_id']]
        assert catalog['kind'] == emission['kind'] == 'output'
        assert catalog['line'] == event['line']
        assert emission['line'] == event['data']['emission_line']
        word = emission['data']['value'][event['data']['fixture_offset']]
        assert divmod(word, 65536) == (event['data']['delta_ticks'], event['data']['catalog_index'])
        assert emission['variables']['page'] == event['data']['fixture_page']
    assert provider.asset('Synthetic', 'audio.wav') == source.with_suffix('.wav')
    assert provider.asset('Synthetic', 'performance.mid') == source.with_suffix('.mid')


@pytest.mark.parametrize('suffix', ['.son', '.inputs.json', '.mid', '.wav'])
def test_provider_rejects_stale_source_fixtures_midi_and_audio_even_after_cache(score, suffix):
    source, _ = score
    provider = debug.LocalPerformances(source.parent)
    provider.payload('Synthetic')
    target = source.with_suffix(suffix)
    target.write_bytes(target.read_bytes() + b' ')
    with pytest.raises(ValueError, match='stale|mismatch'):
        provider.payload('Synthetic')
    with pytest.raises(ValueError, match='stale|mismatch'):
        provider.asset('Synthetic', 'audio.wav')


def test_only_registered_identity_and_asset_kinds(score):
    source, _ = score
    provider = debug.LocalPerformances(source.parent)
    for identity in ('../Synthetic', 'Synthetic.son', '/etc/passwd'):
        with pytest.raises(KeyError):
            provider.payload(identity)
    with pytest.raises(KeyError):
        provider.asset('Synthetic', '../Synthetic.wav')


def test_updated_performance_report_allows_deliberate_local_rebuild(score):
    source, _ = score
    source.write_text(source.read_text() + '\n// Local edit followed by a verified rebuild.\n')
    _, _, report = run_score(source, source.with_suffix('.mid'))
    source.with_suffix('.performance-report.json').write_text(json.dumps(report))
    assert debug.LocalPerformances(source.parent).payload('Synthetic')['result']['error'] is None
