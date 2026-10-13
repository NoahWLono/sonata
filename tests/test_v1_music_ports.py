import copy
import mido
import pytest


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, duration): self.now += duration


class Output:
    def __init__(self): self.messages=[]; self.cleanups=[]
    def send(self,message): self.messages.append(message.dict())
    def reset(self): self.cleanups.append('reset')
    def panic(self): self.cleanups.append('panic')


def fixture():
    return {'schema':'sonata-midi-recording','version':1,'duration_us':500000,'messages':[
        {'time_us':0,'message':{'type':'note_on','channel':0,'note':60,'velocity':90}},
        {'time_us':500000,'message':{'type':'note_off','channel':0,'note':60,'velocity':0}}]}


def test_replay_preserves_message_order_and_scales_clock():
    from sonata.ports import replay_midi
    port,clock=Output(),Clock()
    report=replay_midi(fixture(),port=port,speed=2,clock=clock,sleep=clock.sleep)
    assert [m['type'] for m in port.messages] == ['note_on','note_off']
    assert clock.now == pytest.approx(.25)
    assert port.cleanups==['reset','panic']
    assert report['sent_messages']==2
    other=Output(); clock2=Clock()
    replay_midi(copy.deepcopy(fixture()),port=other,speed=2,clock=clock2,sleep=clock2.sleep)
    assert other.messages==port.messages


@pytest.mark.parametrize('change', [lambda r:r.update(version=2), lambda r:r.update(duration_us=-1), lambda r:r['messages'][1].update(time_us=-1), lambda r:r['messages'][0]['message'].update(note=True), lambda r:r['messages'][0].update(message={'type':'sysex','data':[1,2]}), lambda r:r['messages'][0].update(time_us=1.5),lambda r:r.update(unknown=1)])
def test_recordings_reject_malformed_messages_before_send(change):
    from sonata.ports import replay_midi
    data=fixture(); change(data); port=Output()
    with pytest.raises(ValueError): replay_midi(data,port=port)
    assert port.messages==[]


def test_interrupted_replay_releases_all_notes():
    from sonata.ports import replay_midi
    port,clock=Output(),Clock()
    report=replay_midi(fixture(),port=port,clock=clock,sleep=clock.sleep,stop=lambda: len(port.messages)>0)
    assert report['stopped'] is True
    assert [m['type'] for m in port.messages]==['note_on']
    assert port.cleanups==['reset','panic']


def test_send_exception_still_releases_notes():
    from sonata.ports import replay_midi
    class Failed(Output):
        def send(self,message): raise RuntimeError('disconnected')
    port=Failed()
    with pytest.raises(RuntimeError,match='disconnected'): replay_midi(fixture(),port=port)
    assert port.cleanups==['reset','panic']


def test_capture_timestamps_and_replays_a_fake_input():
    from sonata.ports import capture_midi,replay_midi
    clock=Clock()
    class Input:
        sent=False
        def iter_pending(self):
            if not self.sent:
                self.sent=True
                yield mido.Message('note_on',note=60,velocity=90)
    recording=capture_midi(seconds=.02,port=Input(),clock=clock,sleep=clock.sleep)
    assert recording['duration_us']==20000
    assert recording['messages'][0]['time_us']==0
    out=Output(); clock=Clock()
    replay_midi(recording,port=out,clock=clock,sleep=clock.sleep)
    assert out.messages[0]['note']==60
    assert clock.now==pytest.approx(.02)


def test_capture_has_a_hard_message_budget():
    from sonata.ports import capture_midi
    class Input:
        def iter_pending(self):
            while True: yield mido.Message('note_on')
    clock=Clock()
    with pytest.raises(ValueError,match='limit'): capture_midi(seconds=1,max_messages=3,port=Input(),clock=clock,sleep=clock.sleep)


def test_midi_file_playback_uses_real_tempo_map(tmp_path):
    from sonata.ports import play_midi
    f=mido.MidiFile(ticks_per_beat=480); t=mido.MidiTrack(); f.tracks.append(t)
    t.append(mido.MetaMessage('set_tempo',tempo=1000000))
    t.append(mido.Message('note_on',note=60,velocity=90))
    t.append(mido.MetaMessage('set_tempo',tempo=500000,time=480))
    t.append(mido.Message('note_off',note=60,time=480))
    path=tmp_path/'tempo.mid'; f.save(path)
    port,clock=Output(),Clock()
    play_midi(path,port=port,clock=clock,sleep=clock.sleep)
    assert clock.now==pytest.approx(1.5)


def test_recording_inputs_selects_sounding_note_on_and_preserves_timestamps():
    from sonata.ports import recording_inputs
    record=fixture()
    record['messages'].insert(1,{'time_us':12,'message':{'type':'note_on','channel':1,'note':65,'velocity':0}})
    record['messages'].insert(2,{'time_us':14,'message':{'type':'control_change','channel':1,'control':1,'value':20}})
    record['messages'].insert(3,{'time_us':18,'message':{'type':'note_on','channel':1,'note':67,'velocity':80}})
    assert recording_inputs(record)==[[60,67],[90,80],[0,18]]
    assert recording_inputs(record,max_notes=2)==recording_inputs(record)
    with pytest.raises(ValueError,match='limit'): recording_inputs(record,max_notes=1)
    with pytest.raises(ValueError): recording_inputs(record,max_notes=5000)


def test_recorded_inputs_drive_repeatable_sonata_execution():
    from sonata.ports import recording_inputs
    from sonata.language import parse
    from sonata.runtime import execute
    inputs=recording_inputs(fixture())
    source=parse('let pitches=input(0); return pitches[0];')
    first=execute(source,inputs=inputs)
    assert first==execute(source,inputs=inputs)
    assert first['return_value']==60 and first['error'] is None


def test_malformed_midi_message_type_is_a_validation_error():
    from sonata.ports import validate_recording
    record=fixture(); record['messages'][0]['message']['type']=[]
    with pytest.raises(ValueError): validate_recording(record)
