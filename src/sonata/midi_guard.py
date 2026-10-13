"""Bounded Standard MIDI File preflight before a general MIDI parser allocates.

Only synchronous SMF 0/1 with PPQ timing is supported. This scanner does not
interpret music; it bounds lengths, event counts, integers and status bytes.
"""
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 300_000


def checked_midi_bytes(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("MIDI file exceeds 8 MiB limit")
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("Invalid or truncated MIDI header")
    size = int.from_bytes(data[4:8], "big")
    if not 6 <= size <= 1024 or 8 + size > len(data):
        raise ValueError("Invalid MIDI header length")
    kind = int.from_bytes(data[8:10], "big")
    tracks = int.from_bytes(data[10:12], "big")
    ppq = int.from_bytes(data[12:14], "big")
    if kind not in (0,1) or not 1 <= tracks <= 64 or (kind == 0 and tracks != 1) or not 0 < ppq < 0x8000:
        raise ValueError("Only bounded synchronous PPQ MIDI 0/1 is supported")
    cursor, events = 8 + size, 0

    def vlq(position, end):
        value = 0
        for _ in range(4):
            if position >= end:
                raise ValueError("Truncated MIDI variable-length quantity")
            byte = data[position]
            position += 1
            value = (value << 7) | (byte & 127)
            if byte < 128:
                return value, position
        raise ValueError("MIDI VLQ exceeds four bytes")

    for _ in range(tracks):
        if cursor + 8 > len(data) or data[cursor:cursor+4] != b"MTrk":
            raise ValueError("Missing MIDI track")
        length = int.from_bytes(data[cursor+4:cursor+8], "big")
        cursor += 8
        end = cursor + length
        if end > len(data):
            raise ValueError("Truncated MIDI track")
        running, absolute = None, 0
        while cursor < end:
            events += 1
            if events > MAX_EVENTS:
                raise ValueError("MIDI event limit exceeded")
            delta, cursor = vlq(cursor,end)
            absolute += delta
            if absolute > 0x0FFFFFFF or cursor >= end:
                raise ValueError("Invalid MIDI event time or missing status")
            status = data[cursor]
            if status >= 128:
                cursor += 1
            elif running is not None:
                status = running
            else:
                raise ValueError("MIDI running status without a channel message")
            if 0x80 <= status < 0xF0:
                running = status
                count = 1 if status >> 4 in (0xC,0xD) else 2
                if cursor + count > end or any(byte >= 128 for byte in data[cursor:cursor+count]):
                    raise ValueError("Invalid MIDI channel data")
                cursor += count
            elif status in (0xF0,0xF7,0xFF):
                running = None
                if status == 0xFF:
                    if cursor >= end or data[cursor] >= 128:
                        raise ValueError("Invalid MIDI meta event")
                    cursor += 1
                length, cursor = vlq(cursor,end)
                if cursor + length > end:
                    raise ValueError("Truncated MIDI payload")
                cursor += length
            else:
                raise ValueError("Unsupported MIDI system status")
        cursor = end
    if cursor != len(data):
        raise ValueError("Unexpected data after MIDI tracks")
    return data
