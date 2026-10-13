"""Test recorded MIDI replay with a simulated port and clock; no device I/O."""
import json
from pathlib import Path
from sonata.ports import replay_midi


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Output:
    def __init__(self):
        self.messages = []
        self.cleanup = []

    def send(self, message):
        self.messages.append(message.dict())

    def reset(self):
        self.cleanup.append('reset')

    def panic(self):
        self.cleanup.append('panic')


if __name__ == '__main__':
    recording = json.loads(Path(__file__).with_name('recording.json').read_text())
    clock, port = Clock(), Output()
    report = replay_midi(recording, port=port, clock=clock, sleep=clock.sleep)
    assert report['sent_messages'] == 2
    assert clock.now == .5
    assert port.cleanup == ['reset', 'panic']
    print(json.dumps({'report': report, 'sent': port.messages, 'cleanup': port.cleanup}, indent=2))
