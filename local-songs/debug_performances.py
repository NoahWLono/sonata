"""Opt-in local song performances with provenance back to executed SONATA output.

The scheduled MIDI projection is a playback view, not an interpreter trace. Each
projected event identifies both the catalog print and the executed page emission.
"""
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import io
import json
from pathlib import Path
import threading
import wave

import mido
from score_bridge import RADIX, canonical_midi, decode_output, run_score

SONGS = {
    'Megalovania': 'Megalovania',
    'BADAPPLE': 'Bad Apple!!',
    'ACruelAngelsThesis': "A Cruel Angel's Thesis",
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def project_performance(midi, result):
    """Project verified output messages on a global, tempo-aware playback clock."""
    output_events = [event for event in result['trace'] if event['kind'] == 'output']
    if [event['data']['value'] for event in output_events] != result['output']:
        raise ValueError('Executed output does not match interpreter trace')
    if canonical_midi(decode_output(result['output'], result['return_value'])) != canonical_midi(midi):
        raise ValueError('MIDI does not match executed output')
    header = result['output'][0]
    catalog_count = header[5]
    catalog = output_events[1:1 + catalog_count]
    cursor, scheduled = 1 + catalog_count, []
    for track_id, track in enumerate(midi.tracks):
        _, page_count, _ = result['output'][cursor]
        cursor += 1
        absolute, track_event = 0, 0
        for _ in range(page_count):
            emission = output_events[cursor]
            cursor += 1
            page = emission['variables'].get('page')
            if type(page) is not int:
                raise ValueError('Performance page has no executed input provenance')
            for offset, word in enumerate(emission['data']['value']):
                delta, index = divmod(word, RADIX)
                absolute += delta
                message = track[track_event]
                meaning = {key: value for key, value in message.dict().items() if key not in ('type', 'time')}
                meaning.update(track=track_id, track_event=track_event, catalog_index=index,
                               delta_ticks=delta, absolute_tick=absolute,
                               fixture_page=page, fixture_offset=offset,
                               catalog_trace_id=catalog[index]['id'], emission_trace_id=emission['id'],
                               emission_line=emission['line'])
                scheduled.append({
                    'kind': message.type, 'line': catalog[index]['line'],
                    'col': catalog[index]['col'], 'depth': emission['depth'],
                    'function': 'MIDI performance', 'stack': emission['stack'],
                    'variables': {'track': track_id, 'page': page, 'catalog_index': index},
                    'data': meaning,
                })
                track_event += 1
    scheduled.sort(key=lambda event: (event['data']['absolute_tick'], event['data']['track'], event['data']['track_event']))
    tick, seconds, tempo = 0, 0.0, 500000
    active = defaultdict(deque)
    notes, orphan_offs = [], 0
    for identity, event in enumerate(scheduled):
        data = event['data']
        absolute = data['absolute_tick']
        seconds += mido.tick2second(absolute - tick, midi.ticks_per_beat, tempo)
        tick = absolute
        event.update(id=identity, start=seconds * 2)
        if event['kind'] == 'set_tempo':
            tempo = data['tempo']
        if event['kind'] == 'note_on' and data['velocity'] > 0:
            note = {'id': len(notes), 'event_id': identity, 'start': seconds * 2,
                    'duration': 0.0, 'pitch': data['note'], 'velocity': data['velocity'],
                    'channel': data['channel'], 'voice': data['channel'], 'line': event['line']}
            notes.append(note)
            active[data['channel'], data['note']].append(note)
        elif event['kind'] == 'note_off' or (event['kind'] == 'note_on' and data['velocity'] == 0):
            queue = active[data['channel'], data['note']]
            if queue:
                note = queue.popleft()
                note['duration'] = seconds * 2 - note['start']
            else:
                orphan_offs += 1
    unfinished = 0
    for queue in active.values():
        for note in queue:
            note['duration'] = seconds * 2 - note['start']
            note['unterminated'] = True
            unfinished += 1
    return scheduled, notes, {'orphan_note_offs': orphan_offs, 'unterminated_notes': unfinished,
                              'midi_duration_seconds': seconds}


class LocalPerformances:
    """Fixed local registry; clients can never select arbitrary paths."""
    def __init__(self, directory=None):
        self.directory = Path(directory or Path(__file__).parent).resolve()
        self._cache = {}
        self._lock = threading.Lock()

    def list(self):
        return [{'id': identity, 'name': identity + '.son', 'title': title}
                for identity, title in SONGS.items()]

    def _source(self, identity):
        if identity not in SONGS:
            raise KeyError(identity)
        return self.directory / (identity + '.son')

    def _verified_assets(self, identity):
        source = self._source(identity)
        paths = {suffix: source.with_suffix(suffix) for suffix in ('.son', '.inputs.json', '.mid', '.wav')}
        hashes = {suffix: digest(path) for suffix, path in paths.items()}
        expected = {'source_sha256': hashes['.son'], 'fixture_sha256': hashes['.inputs.json'],
                    'midi_sha256': hashes['.mid']}
        matching_report = None
        for suffix in ('.performance-report.json', '.verification.json'):
            path = source.with_suffix(suffix)
            if path.is_file():
                report = json.loads(path.read_text())
                if all(report.get(key) == value for key, value in expected.items()):
                    matching_report = report
                    break
        if matching_report is None:
            raise ValueError('Source, fixtures, or MIDI is stale; run score_bridge.py perform and render_audio.py again')
        audio = json.loads(source.with_suffix('.audio-report.json').read_text())
        if audio.get('midi_sha256') != hashes['.mid'] or audio.get('wav', {}).get('sha256') != hashes['.wav']:
            raise ValueError('Audio recording is stale; run render_audio.py on the rebuilt MIDI')
        with wave.open(str(paths['.wav']), 'rb') as stream:
            duration = stream.getnframes() / stream.getframerate()
        if abs(duration - audio['wav']['duration_seconds']) > 1e-8:
            raise ValueError('Audio duration report mismatch')
        return source, hashes, duration

    def payload(self, identity):
        with self._lock:
            source, hashes, duration = self._verified_assets(identity)
            fingerprint = tuple(hashes.items())
            cached = self._cache.get(identity)
            if cached and cached[0] == fingerprint:
                return cached[1]
            midi, result, verification = run_score(source)
            # Compare all MIDI events and actual serialization with the exact file
            # whose hash the audio renderer recorded. No timing-only comparison.
            rendered = mido.MidiFile(source.with_suffix('.mid'))
            if canonical_midi(midi) != canonical_midi(rendered):
                raise ValueError('Executed MIDI and audio input mismatch; rebuild the recording')
            serialized = io.BytesIO()
            midi.save(file=serialized)
            if hashlib.sha256(serialized.getvalue()).hexdigest() != hashes['.mid']:
                raise ValueError('Executed MIDI bytes and audio input mismatch; rebuild the recording')
            if verification['source_sha256'] != hashes['.son'] or verification['fixture_sha256'] != hashes['.inputs.json']:
                raise ValueError('Source changed during verification; reload the performance')
            trace, notes, metrics = project_performance(midi, result)
            performance = {
                'id': identity, 'title': SONGS[identity],
                'audio_url': f'/api/performances/{identity}/audio.wav',
                'midi_url': f'/api/performances/{identity}/performance.mid',
                'duration_seconds': duration, 'duration_beats': duration * 2,
                'trace_kind': 'scheduled_midi_projection',
                'trace_description': 'Scheduled MIDI events projected from executed SONATA outputs; not interpreter execution order.',
                'note_description': 'Note rectangles show key-down duration; sustain, instrument envelopes and reverb remain in the recorded audio.',
                'reference_equal': verification['reference_equal'],
                'interpreter_trace_events': len(result['trace']),
                'source_sha256': hashes['.son'], 'midi_sha256': hashes['.mid'],
                **metrics,
            }
            payload = {
                'source': source.read_text(), 'name': source.name,
                'result': {'error': None, 'return_value': result['return_value'],
                           'instructions': result['instructions'], 'trace': trace,
                           'output': [f"{len(trace)} MIDI messages; {len(notes)} notes; interpreter/reference agree."]},
                'notes': notes, 'code_notes': [], 'code_tokens': [], 'performance': performance,
            }
            self._cache[identity] = fingerprint, payload
            return payload

    def asset(self, identity, kind):
        if kind not in ('audio.wav', 'performance.mid'):
            raise KeyError(kind)
        self.payload(identity)  # Recheck every asset request, including cache hits.
        return self._source(identity).with_suffix('.wav' if kind == 'audio.wav' else '.mid')
