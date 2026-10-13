from pathlib import Path
import sys

import mido
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from score_bridge import convert_midi, run_score, canonical_midi


def fixture(path):
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage('track_name', name='Conductor'),
        mido.MetaMessage('set_tempo', tempo=500000),
        mido.MetaMessage('time_signature', numerator=3, denominator=4),
        mido.MetaMessage('set_tempo', tempo=750000, time=480),
        mido.MetaMessage('end_of_track', time=960),
    ]))
    midi.tracks.append(mido.MidiTrack([
        mido.Message('program_change', channel=1, program=81),
        mido.Message('control_change', channel=1, control=64, value=127),
        mido.Message('note_on', channel=1, note=62, velocity=87),
        mido.Message('note_on', channel=1, note=62, velocity=93, time=120),
        mido.Message('pitchwheel', channel=1, pitch=-1024),
        mido.Message('note_off', channel=1, note=62, velocity=0, time=120),
        mido.Message('note_on', channel=1, note=62, velocity=0, time=120),
        mido.Message('note_off', channel=1, note=62, velocity=0),
        mido.Message('control_change', channel=1, control=64, value=0, time=120),
        mido.Message('note_on', channel=9, note=36, velocity=100),
        mido.Message('note_off', channel=9, note=36, time=120),
        mido.MetaMessage('end_of_track', time=100000),
    ]))
    midi.save(path)
    return midi


def test_exact_channel_meta_tracks_and_timing_round_trip(tmp_path):
    original = fixture(tmp_path/'input.mid')
    target = tmp_path/'Example.son'
    convert_midi(tmp_path/'input.mid', target, page_size=4)
    restored, execution, verification = run_score(target, tmp_path/'output.mid')
    assert canonical_midi(restored) == canonical_midi(original)
    assert canonical_midi(mido.MidiFile(tmp_path/'output.mid')) == canonical_midi(original)
    assert verification['reference_equal']
    assert execution['error'] is None
    assert execution['return_value'] == sum(map(len, original.tracks))
    assert original.length == restored.length


def test_stream_fixture_has_effect_on_executed_performance(tmp_path):
    import json
    fixture(tmp_path/'input.mid')
    target=tmp_path/'Example.son'
    convert_midi(tmp_path/'input.mid', target, page_size=4)
    first, _, _ = run_score(target)
    source=target.with_suffix('.inputs.json')
    pages=json.loads(source.read_text())
    pages[0][0] += 65536 * 120
    source.write_text(json.dumps(pages))
    second, _, _ = run_score(target)
    assert canonical_midi(first) != canonical_midi(second)
    assert second.tracks[0][0].time == first.tracks[0][0].time + 120


def test_reject_malformed_fixture_and_extra_records(tmp_path):
    import json
    fixture(tmp_path/'input.mid')
    target=tmp_path/'Example.son'
    convert_midi(tmp_path/'input.mid', target)
    path=target.with_suffix('.inputs.json')
    data=json.loads(path.read_text())
    data[0][0]=65535
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='catalog'):
        run_score(target)


def test_reproducible_generated_files(tmp_path):
    fixture(tmp_path/'input.mid')
    a=tmp_path/'a'; b=tmp_path/'b'; a.mkdir(); b.mkdir()
    convert_midi(tmp_path/'input.mid', a/'Example.son')
    convert_midi(tmp_path/'input.mid', b/'Example.son')
    assert (a/'Example.son').read_bytes() == (b/'Example.son').read_bytes()
    assert (a/'Example.inputs.json').read_bytes() == (b/'Example.inputs.json').read_bytes()
