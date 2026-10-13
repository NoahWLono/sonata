"""Generated listening lessons must retain computational and musical evidence."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import wave

import numpy as np
import pytest

from sonata.codec import import_program
from sonata.language import canonical, parse
from sonata.midi import read_midi, TICKS_PER_BEAT
from sonata.runtime import execute

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def lesson_pack(tmp_path_factory):
    path = ROOT / 'scripts/v1_demos.py'
    spec = importlib.util.spec_from_file_location('v1_demos', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path_factory.mktemp('listening')
    manifest = module.generate(output)
    return output, manifest, module


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def note_signature(note):
    return (round(note['start']*TICKS_PER_BEAT), round((note['start']+note['duration'])*TICKS_PER_BEAT),
            note['pitch'], note['velocity'], note['channel'])


def test_listening_pack_covers_requested_cases(lesson_pack):
    _, manifest, _ = lesson_pack
    assert set(manifest['clips']) == {
        'branch_true', 'branch_false', 'call_return', 'array_changes',
        'assertion_pass', 'assertion_error', 'range_inside', 'range_above', 'range_below',
        'watch_all', 'watch_total', 'semantic_original', 'semantic_formatted',
        'legacy_original', 'legacy_formatted', 'score_original', 'score_edited',
        'module_bundle', 'off_by_one',
    }
    assert manifest['human_participant_data'] is False
    assert manifest['comparisons']['semantic_formatting']['same_symbolic_performance'] is True
    assert manifest['comparisons']['semantic_formatting']['same_wav'] is True
    assert manifest['comparisons']['legacy_formatting']['same_symbolic_performance'] is False
    assert manifest['comparisons']['off_by_one']['equal'] is False


def test_every_clip_is_audible_located_and_midi_roundtrips(lesson_pack):
    output, manifest, _ = lesson_pack
    for name, info in manifest['clips'].items():
        directory = output / name
        source = (directory / 'source.son').read_text()
        result, notes = read(directory / 'trace.json'), read(directory / 'notes.json')
        profile, inputs = read(directory / 'profile.json'), read(directory / 'inputs.json')
        assert info['return_value'] == result['return_value']
        assert info['checks_passed']
        assert notes
        events = {event['id']: event for event in result['trace']}
        for note in notes:
            event = events[note['event_id']]
            assert note['line'] == event['line']
            assert event['id']*profile['event_stride'] <= note['start'] < (event['id']+1)*profile['event_stride']
        assert Counter(map(note_signature, read_midi(directory / 'execution.mid'))) == Counter(map(note_signature, notes))
        with wave.open(str(directory / 'execution.wav')) as audio:
            samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(float)
            assert np.sqrt(np.mean(samples**2)) > 0
            target = max(n['start']+n['duration'] for n in notes)*60/manifest['bpm'] + .2
            assert abs(audio.getnframes()/audio.getframerate() - target) <= 2/audio.getframerate()
        rebuilt = import_program(directory / 'code.mid')
        assert canonical(rebuilt) == canonical(parse(source))
        playback = execute(rebuilt, inputs=inputs)
        assert playback['return_value'] == result['return_value']
        assert (playback['error'] or {}).get('kind') == (result['error'] or {}).get('kind')


def test_teaching_cues_have_correct_intervals_and_event_provenance(lesson_pack):
    root, _, _ = lesson_pack
    for name, interval in [('branch_true',5), ('branch_false',3)]:
        notes = read(root/name/'notes.json')
        assert len(notes) == 2
        assert notes[1]['pitch'] - notes[0]['pitch'] == interval
    failed = read(root/'assertion_error'/'trace.json')
    assert failed['error']['kind'] == 'AssertionError'
    notes = [n for n in read(root/'assertion_error'/'notes.json') if n['event_id'] == failed['trace'][-1]['id']]
    root_pitch = notes[0]['pitch']
    assert sorted(n['pitch']-root_pitch for n in notes) == [0,1,6]
    assert not any(n.get('cue') for n in read(root/'range_inside'/'notes.json'))
    assert any(n.get('cue') == 'above_range' for n in read(root/'range_above'/'notes.json'))
    assert any(n.get('cue') == 'below_range' for n in read(root/'range_below'/'notes.json'))
    arrays = read(root/'array_changes'/'trace.json')
    assert arrays['output'] == [[5,1,4], [1,5,4], [1,4,5]]
    array_notes = read(root/'array_changes'/'notes.json')
    last_output = [e for e in arrays['trace'] if e['kind'] == 'output'][-1]
    ascending = [n['pitch'] for n in array_notes if n['event_id'] == last_output['id']]
    assert len(ascending) == 3 and ascending[0] < ascending[1] < ascending[2]
    calls = read(root/'call_return'/'trace.json')['trace']
    call_notes = read(root/'call_return'/'notes.json')
    for event in [e for e in calls if e['kind'] in {'call','return'}]:
        pitches = [n['pitch'] for n in call_notes if n['event_id'] == event['id']]
        assert [pitch-pitches[0] for pitch in pitches] == ([0,7] if event['kind'] == 'call' else [0,7,12])
    full = read(root/'watch_all'/'notes.json')
    watched = read(root/'watch_total'/'notes.json')
    trace = read(root/'watch_total'/'trace.json')['trace']
    assert 0 < len(watched) < len(full)
    assert [n['event_id'] for n in watched] == [e['id'] for e in trace if e['kind'] in {'declare','assign'} and e['data'].get('name') == 'total']
    assert all(n['start'] == n['event_id']*.25 for n in watched)


def test_score_edit_and_module_use_real_roundtrip_and_reference(lesson_pack):
    root, manifest, _ = lesson_pack
    assert manifest['clips']['score_original']['return_value'] == 15
    assert manifest['clips']['score_edited']['return_value'] == 21
    assert manifest['score_edit']['old_token'] == '6'
    assert manifest['score_edit']['new_token'] == '7'
    assert manifest['score_edit']['decoded_return_value'] == 21
    assert manifest['clips']['module_bundle']['return_value'] == 55
    assert read(root/'module_bundle'/'independent-verification.json')['passed']


def test_listening_pack_is_byte_reproducible(lesson_pack, tmp_path):
    original, _, module = lesson_pack
    module.generate(tmp_path)
    names = {p.relative_to(original) for p in original.rglob('*') if p.is_file()}
    assert names == {p.relative_to(tmp_path) for p in tmp_path.rglob('*') if p.is_file()}
    for name in names:
        assert hashlib.sha256((original/name).read_bytes()).digest() == hashlib.sha256((tmp_path/name).read_bytes()).digest(), name
