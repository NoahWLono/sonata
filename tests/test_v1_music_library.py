from fractions import Fraction
import json
import wave
import mido
import pytest


def test_scale_chord_and_rhythm_primitives():
    from sonata.musiclib import scale, chord, rhythm
    assert scale(60,'major') == [60,62,64,65,67,69,71,72]
    assert chord(60,'minor') == [60,63,67]
    assert rhythm(['1/3','1/3','1/3']) == [Fraction(1,3)]*3
    with pytest.raises(ValueError): scale(125,'major')
    with pytest.raises(ValueError): rhythm(['0'])


def test_named_voices_exact_schedule_and_program_export(tmp_path):
    from sonata.musiclib import Score
    score = Score()
    score.add_voice('piano',channel=0,program=1)
    score.add_voice('strings',channel=1,program=48)
    score.pattern('piano',[60,62,64],['1/3']*3)
    score.note('strings',48,start=0,duration=1)
    assert score.events[2]['start'] == Fraction(2,3)
    report = score.export(tmp_path)
    assert report['note_count']==4
    midi = mido.MidiFile(tmp_path/'composition.mid')
    assert {(m.channel,m.program) for t in midi.tracks for m in t if m.type=='program_change'} == {(0,1),(1,48)}
    assert len(report['stems']['voices'])==2
    assert (tmp_path/'stems'/'piano.mid').exists()
    assert json.loads((tmp_path/'manifest.json').read_text())['voices']['piano']['program']==1


def test_stems_use_safe_names_and_keep_global_time(tmp_path):
    from sonata.musiclib import export_stems
    from sonata.midi import read_midi
    notes=[{'start':2,'duration':.5,'pitch':60,'channel':0,'voice':'../../evil'}]
    report=export_stems(notes,tmp_path)
    assert report['voices'][0]['voice']=='../../evil'
    assert read_midi(tmp_path/report['voices'][0]['midi'])[0]['start']==2
    assert (tmp_path/report['voices'][0]['wav']).exists()
    assert report['voices'][0]['midi']=='voice-000.mid'


def test_score_rejects_ambiguous_voice_channels_and_bad_rational_grid():
    from sonata.musiclib import Score
    s=Score(); s.add_voice('one',channel=0)
    with pytest.raises(ValueError): s.add_voice('two',channel=0)
    with pytest.raises(ValueError): s.add_voice('../bad')
    with pytest.raises(ValueError): s.note('one',60,start=0,duration='1/7')
    with pytest.raises(ValueError): s.note('one',60,start=0,duration=True)


def test_stem_filename_collision_terminates(tmp_path):
    import subprocess
    import sys
    code = '''from sonata.musiclib import export_stems
from pathlib import Path
notes=[{'pitch':60+i,'start':0,'duration':.1,'voice':v,'channel':i} for i,v in enumerate(['voice-002-2','a','A'])]
report=export_stems(notes,Path(__import__('sys').argv[1]))
assert len({v['midi'].casefold() for v in report['voices']})==3
'''
    subprocess.run([sys.executable,'-c',code,str(tmp_path)],check=True,timeout=3)


def test_pattern_bounds_iterable_consumption(monkeypatch):
    import sonata.musiclib as library
    monkeypatch.setattr(library,'MAX_NOTES',3)
    def pitches():
        for i in range(5): yield 60
        raise RuntimeError('consumed too many pitches')
    score=library.Score(); score.add_voice('piano')
    with pytest.raises(ValueError,match='limit'): score.pattern('piano',pitches(),[1]*3)


def test_windows_reserved_voice_names_do_not_become_stem_paths(tmp_path):
    from sonata.musiclib import Score, export_stems
    with pytest.raises(ValueError): Score().add_voice('CON')
    report=export_stems([{'pitch':60,'start':0,'duration':.1,'voice':'CON'}],tmp_path)
    assert report['voices'][0]['midi']=='voice-000.mid'
