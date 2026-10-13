"""Synthetic HTTP tests for opt-in recorded performances."""
import json
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from sonata.server import create_server


class SyntheticPerformances:
    def __init__(self, directory):
        self.audio = directory / 'recording.wav'
        self.audio.write_bytes(bytes(range(256)) * 1024)
        self.midi = directory / 'recording.mid'
        self.midi.write_bytes(b'MThd\x00\x00\x00\x06')
        self.stale = False

    def list(self):
        return [{'id': 'synthetic', 'name': 'Synthetic.son', 'title': 'Synthetic'}]

    def payload(self, identity):
        if identity != 'synthetic':
            raise KeyError(identity)
        if self.stale:
            raise ValueError('Source or recording is stale; rebuild the performance')
        return {'source': 'return 1;', 'result': {'return_value': 1}, 'notes': [],
                'performance': {'id': identity}}

    def asset(self, identity, kind):
        self.payload(identity)
        return {'audio.wav': self.audio, 'performance.mid': self.midi}[kind]


@contextmanager
def running(provider=None):
    server = create_server('return 1;', port=0, performance_provider=provider)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_performances_are_explicitly_opt_in():
    with running() as url:
        assert json.load(urlopen(url + '/api/performances')) == {'performances': []}
        with pytest.raises(HTTPError) as error:
            urlopen(url + '/api/performances/synthetic')
        assert error.value.code == 404


def test_registered_payload_and_assets_only(tmp_path):
    provider = SyntheticPerformances(tmp_path)
    with running(provider) as url:
        assert json.load(urlopen(url + '/api/performances'))['performances'] == provider.list()
        assert json.load(urlopen(url + '/api/performances/synthetic'))['result']['return_value'] == 1
        with urlopen(url + '/api/performances/synthetic/audio.wav') as response:
            assert response.read() == provider.audio.read_bytes()
            assert response.headers['Content-Type'] == 'audio/wav'
            assert response.headers['Accept-Ranges'] == 'bytes'
        assert urlopen(url + '/api/performances/synthetic/performance.mid').read() == provider.midi.read_bytes()
        for route in ('unknown', '../recording.wav', 'synthetic/../recording.wav', 'synthetic/source.py'):
            with pytest.raises(HTTPError) as error:
                urlopen(url + '/api/performances/' + route)
            assert error.value.code == 404
        provider.stale = True
        with pytest.raises(HTTPError) as error:
            urlopen(url + '/api/performances/synthetic/audio.wav')
        assert error.value.code == 409


@pytest.mark.parametrize(('range_value', 'start', 'end'), [
    ('bytes=44-87', 44, 87), ('bytes=262100-', 262100, 262143),
    ('bytes=-10', 262134, 262143), ('bytes=262140-999999', 262140, 262143),
])
def test_audio_range_requests_seek_without_full_download(tmp_path, range_value, start, end):
    provider = SyntheticPerformances(tmp_path)
    with running(provider) as url:
        with urlopen(Request(url + '/api/performances/synthetic/audio.wav', headers={'Range': range_value})) as response:
            assert response.status == 206
            assert response.headers['Content-Range'] == f'bytes {start}-{end}/262144'
            assert int(response.headers['Content-Length']) == end - start + 1
            assert response.read() == provider.audio.read_bytes()[start:end + 1]


@pytest.mark.parametrize('range_value', ['bytes=262144-', 'bytes=10-4', 'bytes=0-1,3-4', 'bytes=-0', 'nonsense', 'bytes=-'])
def test_unsatisfiable_or_unsupported_ranges(tmp_path, range_value):
    with running(SyntheticPerformances(tmp_path)) as url:
        with pytest.raises(HTTPError) as error:
            urlopen(Request(url + '/api/performances/synthetic/audio.wav', headers={'Range': range_value}))
        assert error.value.code == 416
        assert error.value.headers['Content-Range'] == 'bytes */262144'


def test_performance_routes_retain_origin_and_host_guards(tmp_path):
    with running(SyntheticPerformances(tmp_path)) as url:
        for headers in ({'Origin': 'https://foreign.invalid'}, {'Host': 'foreign.invalid'}):
            with pytest.raises(HTTPError) as error:
                urlopen(Request(url + '/api/performances/synthetic/audio.wav', headers=headers))
            assert error.value.code == 403
