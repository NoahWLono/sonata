"""Create a small original score; no MIDI device or external soundfont needed."""
import argparse
from pathlib import Path
from sonata.musiclib import Score, chord


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', default='artifacts/composition')
    args = parser.parse_args()
    score = Score(bpm=108, palette='classical')
    score.add_voice('melody', channel=0, program=0)
    score.add_voice('answer', channel=1, program=40)
    score.add_voice('bass', channel=2, program=42)
    score.pattern('melody', [60, 62, 64, 67, 64, 62, 60, 64, 67, 72, 71, 67], ['1/3'] * 12)
    score.pattern('answer', [72, 67, 64, 62, 64, 67], ['1/2'] * 6, start=1)
    score.pattern('bass', [48, 43, 45, 48], [1] * 4)
    for pitch in chord(60, 'major'):
        score.note('melody', pitch, start=4, duration=2, velocity=72)
    report = score.export(Path(args.output))
    print(f"Exported {report['note_count']} notes to {args.output}")


if __name__ == '__main__':
    main()
