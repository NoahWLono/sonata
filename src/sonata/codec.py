"""SC1: a reversible note grammar. Program content lives entirely in notes.

Reserved tokens have individual pitches. Identifiers and decimal literals use
diatonic nibble melodies; checksum and framing are audible notes too.
"""
from collections import defaultdict
import re
import zlib

from .language import parse, format_source, _tokens
from .midi import write_midi, read_midi

TOKENS = ("let", "for", "in", "if", "else", "while", "fn", "return", "true", "false",
          "print", "len", "{", "}", "(", ")", "[", "]", ";", ",", "=", "..",
          "+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||", "!")
TOKEN_PITCHES = {token: 36 + i for i, token in enumerate(TOKENS)}
PITCH_TOKENS = {pitch: token for token, pitch in TOKEN_PITCHES.items()}
DIGITS = (48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74)
IDENT, NUMBER, DELIMITER, CHECKSUM = 84, 85, 86, 87
HEADER, FOOTER = (96, 100, 103), (95, 99, 102)
CELL, LENGTH = .125, .09375  # 60 and 45 ticks at 480 PPQ
MAX_NOTES = 100_000


def encode_ast(ast):
    source = format_source(ast, compact=True)
    tokens = [t for t in _tokens(source) if t.text != "<eof>"]
    notes, cell = [], 0

    def emit(pitches, channel=0, line=0, token=None):
        nonlocal cell
        for pitch in pitches:
            notes.append({"id": len(notes), "event_id": None, "line": line,
                          "start": cell * CELL, "duration": LENGTH, "pitch": pitch,
                          "channel": channel, "velocity": 80, "voice": "code", "token": token})
        cell += 1
        if len(notes) > MAX_NOTES:
            raise ValueError("Musical source exceeds note limit")

    emit(HEADER)
    for token in tokens:
        text = token.text
        if text in TOKEN_PITCHES:
            emit([TOKEN_PITCHES[text]], line=token.line, token=text)
        else:
            emit([NUMBER if text.isdecimal() else IDENT], line=token.line, token=text)
            for byte in text.encode("ascii"):
                emit([DIGITS[byte >> 4]], 1, token.line, text)
                emit([DIGITS[byte & 15]], 1, token.line, text)
            emit([DELIMITER], line=token.line, token=text)
    checksum = zlib.crc32(" ".join(t.text for t in tokens).encode("ascii"))
    emit([CHECKSUM])
    for nibble in f"{checksum:08x}":
        emit([DIGITS[int(nibble, 16)]], 2)
    emit(FOOTER)
    return notes


def decode_notes(notes):
    if not notes or len(notes) > MAX_NOTES:
        raise ValueError("Empty or oversized musical code")
    cells = defaultdict(list)
    for note in notes:
        raw = note["start"] / CELL
        position = round(raw)
        if position < 0 or abs(raw - position) > 1e-7 or abs(note["duration"] - LENGTH) > 1e-7:
            raise ValueError("Code score is not on the SC1 rhythmic grid")
        cells[position].append((note["channel"], note["pitch"]))
    if sorted(cells) != list(range(len(cells))):
        raise ValueError("Missing or displaced code cell")
    rows = [sorted(cells[i]) for i in range(len(cells))]
    if rows[0] != [(0, p) for p in HEADER] or rows[-1] != [(0, p) for p in FOOTER]:
        raise ValueError("Missing SC1 header or footer chord")
    tokens, i = [], 1

    def singleton(index):
        if index >= len(rows) - 1 or len(rows[index]) != 1:
            raise ValueError("Expected one note in code cell")
        return rows[index][0]

    while i < len(rows) - 1:
        channel, pitch = singleton(i)
        if channel != 0:
            raise ValueError("Expected operation voice")
        i += 1
        if pitch == CHECKSUM:
            break
        if pitch in PITCH_TOKENS:
            tokens.append(PITCH_TOKENS[pitch])
        elif pitch in (IDENT, NUMBER):
            nibbles = []
            while singleton(i) != (0, DELIMITER):
                ch, p = singleton(i)
                if ch != 1 or p not in DIGITS:
                    raise ValueError("Invalid operand melody")
                nibbles.append(DIGITS.index(p))
                i += 1
            i += 1
            if not nibbles or len(nibbles) % 2:
                raise ValueError("Incomplete operand melody")
            try:
                token = bytes(nibbles[j] * 16 + nibbles[j+1] for j in range(0, len(nibbles), 2)).decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError("Invalid ASCII operand") from exc
            if not re.fullmatch(r"[0-9]+" if pitch == NUMBER else r"[A-Za-z_][A-Za-z_0-9]*", token):
                raise ValueError("Invalid operand spelling")
            tokens.append(token)
        else:
            raise ValueError("Unknown operation pitch")
    else:
        raise ValueError("Missing checksum melody")
    if len(rows) - 1 - i != 8:
        raise ValueError("Malformed checksum melody")
    checksum = 0
    for j in range(i, i + 8):
        ch, pitch = singleton(j)
        if ch != 2 or pitch not in DIGITS:
            raise ValueError("Invalid checksum note")
        checksum = checksum * 16 + DIGITS.index(pitch)
    source = " ".join(tokens)
    if zlib.crc32(source.encode("ascii")) != checksum:
        raise ValueError("Code score checksum mismatch")
    return parse(source)


def compile_program(ast, path):
    notes = encode_ast(ast)
    write_midi(notes, path)
    return notes


def import_program(path):
    return decode_notes(read_midi(path))
