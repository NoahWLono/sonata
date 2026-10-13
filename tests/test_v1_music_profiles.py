import copy
import pytest
from sonata.language import parse
from sonata.runtime import execute
from sonata.music import sonify


def pitches(notes):
    return [(n['start'], n['duration'], n['pitch'], n['channel'], n['velocity']) for n in notes]


def test_semantic_profile_survives_comment_and_line_changes():
    plain = execute(parse('let x=2; x=x+3; return x;'))['trace']
    spaced = execute(parse('// hello\n\nlet x=2;\n\nx=x+3;\nreturn x;'))['trace']
    assert pitches(sonify(plain, profile={'mapping':'semantic'})) == pitches(sonify(spaced, profile={'mapping':'semantic'}))
    assert {n['line'] for n in sonify(plain, profile={})} != {n['line'] for n in sonify(spaced, profile={})}


def test_filters_preserve_original_positions_and_event_ids():
    trace = execute(parse('let x=2; let y=3; x=x+y; return x;'))['trace']
    profile = {'variables':['x'], 'event_kinds':['assign']}
    notes = sonify(trace, profile=profile)
    event = next(e for e in trace if e['kind']=='assign')
    assert {n['event_id'] for n in notes} == {event['id']}
    assert notes[0]['start'] == event['id']*.25
    assert notes[0]['trace_index'] == event['id']
    assert sonify(trace, profile={'event_kinds':[]}) == []


def test_function_filter_and_custom_stride():
    trace = execute(parse('fn f(n) { return n+1; } return f(2);'))['trace']
    notes = sonify(trace, profile={'functions':['f'], 'event_stride':.5})
    assert notes
    assert all(trace[n['event_id']]['function']=='f' for n in notes)
    assert all(n['start'] >= n['event_id']*.5 for n in notes)


def test_ranges_have_monotonic_mapping_and_explicit_cues():
    trace = [{'id':i, 'line':1, 'depth':0, 'kind':'assign', 'function':'main', 'data':{'name':'x','value':v}, 'variables':{'x':v}, 'stack':['main']} for i,v in enumerate([-1,0,5,10,11])]
    notes = sonify(trace, profile={'ranges':{'x':[0,10]}})
    melody = [n for n in notes if not n.get('cue')]
    assert [n['pitch'] for n in melody] == sorted(n['pitch'] for n in melody)
    assert {(n['event_id'],n['cue']) for n in notes if n.get('cue')} == {(0,'below_range'),(4,'above_range')}
    assert pitches(notes) == pitches(sonify(copy.deepcopy(trace), profile={'ranges':{'x':[0,10]}}))


@pytest.mark.parametrize('profile', [{'version':2}, {'mapping':'random'}, {'ranges':{'x':[1,1]}}, {'ranges':{'x':[False,2]}}, {'ranges':{'x':[-2**64,2]}}, {'event_stride':float('nan')}, {'event_kinds':'assign'}, {'unknown':True}])
def test_profile_rejects_invalid_configuration(profile):
    from sonata.profiles import validate_profile
    with pytest.raises(ValueError): validate_profile(profile)


def test_comparison_ignores_locations_but_preserves_boolean_integer_distinction():
    from sonata.comparison import compare_traces
    a = execute(parse('let x=1; return x;'))['trace']
    b = execute(parse('\n\nlet x=1;\nreturn x;'))['trace']
    assert compare_traces(a,b)['equal']
    c = copy.deepcopy(a)
    c[1]['data']['value'] = True
    report = compare_traces(a,c)
    assert not report['equal'] and report['first_divergence']==1
    assert report['window'][1]['equal'] is False
    report = compare_traces(a, a[:-1])
    assert report['first_divergence']==len(a)-1
    assert report['window'][-1]['right'] is None


def test_out_of_range_error_cue_has_no_ambiguous_unison(tmp_path):
    from sonata.midi import write_midi
    trace=[{'id':0,'line':1,'depth':0,'kind':'error','function':'main','data':{'name':'x','value':99},'variables':{'x':99},'stack':['main']}]
    notes=sonify(trace,profile={'ranges':{'x':[0,10]}})
    assert all(n['duration']>0 for n in notes)
    assert len({(n['channel'],n['pitch'],n['start']) for n in notes})==len(notes)
    assert any(n.get('cue')=='above_range' for n in notes)
    write_midi(notes,tmp_path/'range.mid')


def test_profile_rejects_array_slots_below_midi_resolution():
    trace=[{'id':0,'line':1,'depth':0,'kind':'assign','function':'main','data':{'name':'a','value':[0]*4096},'variables':{},'stack':['main']}]
    with pytest.raises(ValueError,match='stride|resolution'):
        sonify(trace,profile={'event_stride':1/32})
