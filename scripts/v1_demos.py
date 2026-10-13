"""Rebuild v1 listening lessons from real executions, without participant data."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import wave

import numpy as np

from sonata.audio import render_wav
from sonata.codec import compile_program, import_program
from sonata.comparison import compare_traces
from sonata.language import canonical, format_source, parse
from sonata.loader import load_source
from sonata.midi import read_midi, write_midi, TICKS_PER_BEAT
from sonata.music import sonify
from sonata.profiles import validate_profile
from sonata.reference import evaluate
from sonata.runtime import execute
from sonata.studio import code_score, edit_score
from sonata.validation import verify

ROOT = Path(__file__).resolve().parents[1]
BPM = 120
PALETTE = 'classical'
SEMANTIC = {'version': 1, 'mapping': 'semantic'}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def performance(notes):
    return [(round(n['start']*TICKS_PER_BEAT), round((n['start']+n['duration'])*TICKS_PER_BEAT),
             n['pitch'], n['velocity'], n['channel']) for n in notes]


def behavior(result):
    return json.dumps({key: result[key] for key in ('return_value', 'output', 'globals')}, sort_keys=True)


def generate(output=None, root=ROOT):
    """Write a self-contained lesson pack; paths and wall-clock data stay out."""
    root = Path(root)
    output = Path(output) if output is not None else root / 'audio' / 'v1'
    output.mkdir(parents=True, exist_ok=True)
    sources = root / 'examples' / 'listening'
    source = lambda name: (sources / (name + '.son')).read_text(encoding='utf-8')
    fixture = lambda name: json.loads((sources / (name + '.json')).read_text(encoding='utf-8'))
    manifest = {'schema': 'sonata-listening-lessons-1', 'bpm': BPM, 'palette': PALETTE,
                'human_participant_data': False, 'clips': {}, 'comparisons': {}}
    runs = {}

    def record(name, text, *, inputs=None, profile=None, expected=None, error=None, lesson=''):
        directory = output / name
        directory.mkdir(exist_ok=True)
        settings = validate_profile(SEMANTIC if profile is None else profile)
        inputs = [] if inputs is None else inputs
        ast = parse(text)
        result = execute(ast, inputs=inputs)
        reference = evaluate(text, inputs=inputs)
        actual_error = (result['error'] or {}).get('kind')
        if result['return_value'] != expected or actual_error != error:
            raise AssertionError(f'{name}: unexpected result {result["return_value"]!r} / {actual_error!r}')
        notes = sonify(result['trace'], palette=PALETTE, profile=settings)
        (directory / 'source.son').write_text(text, encoding='utf-8')
        save(directory / 'inputs.json', inputs)
        save(directory / 'profile.json', settings)
        save(directory / 'trace.json', result)
        save(directory / 'notes.json', notes)
        compile_program(ast, directory / 'code.mid')
        restored = import_program(directory / 'code.mid')
        (directory / 'decoded.son').write_text(format_source(restored), encoding='utf-8')
        replay = execute(restored, inputs=inputs)
        write_midi(notes, directory / 'execution.mid', bpm=BPM, palette=PALETTE)
        render_wav(notes, directory / 'execution.wav', bpm=BPM, palette=PALETTE)
        # Read the durable audio and MIDI back; never use renderer-reported RMS
        # or duration as the only evidence that these files contain the score.
        with wave.open(str(directory / 'execution.wav')) as audio:
            frames, rate = audio.getnframes(), audio.getframerate()
            samples = np.frombuffer(audio.readframes(frames), dtype='<i2').astype(np.float64) / 32768
        duration = frames / rate
        rms = float(np.sqrt(np.mean(samples*samples)))
        lookup = {event['id']: event for event in result['trace']}
        stride = settings['event_stride']
        target = max(n['start'] + n['duration'] for n in notes) * 60 / BPM + .2
        checks = {
            'reference_observables_match': behavior(result) == behavior(reference),
            'reference_error_kind_matches': actual_error == (reference['error'] or {}).get('kind'),
            'canonical_ast_roundtrip': canonical(ast) == canonical(restored),
            'roundtrip_observables_match': behavior(result) == behavior(replay),
            'roundtrip_error_kind_matches': actual_error == (replay['error'] or {}).get('kind'),
            'note_event_ids_known': all(n['event_id'] in lookup for n in notes),
            'note_source_locations_match': all(n['line'] == lookup[n['event_id']]['line'] for n in notes),
            'note_time_cells_match': all(n['event_id']*stride <= n['start'] < (n['event_id']+1)*stride for n in notes),
            'runtime_midi_exact': Counter(performance(notes)) == Counter(performance(read_midi(directory / 'execution.mid'))),
            'wav_non_silent': rms > 0,
            'wav_duration_matches': abs(duration-target) <= 2/rate,
        }
        if not all(checks.values()):
            raise AssertionError((name, checks))
        save(directory / 'validation.json', {'checks': checks, 'passed': True,
             'scope': 'Independent evaluator observables and expected assertion errors, score roundtrip, note provenance, and re-read MIDI/WAV. Shared parser and codec remain trust dependencies.'})
        info = {'lesson': lesson, 'return_value': result['return_value'], 'error_kind': actual_error,
                'trace_events': len(result['trace']), 'notes': len(notes),
                'audible_event_ids': sorted({n['event_id'] for n in notes}),
                'duration_seconds': duration, 'rms': rms, 'checks_passed': True}
        manifest['clips'][name] = info
        runs[name] = {'result': result, 'notes': notes}

    for name, expected in [('branch_true', 1), ('branch_false', 0)]:
        record(name, source('branch'), inputs=fixture(name), expected=expected,
               profile={**SEMANTIC, 'event_kinds': ['branch'], 'event_stride': 1},
               lesson='Only the branch decision: true forms a perfect fourth, false a minor third.')
    record('call_return', source('call_return'), expected=6,
           profile={**SEMANTIC, 'event_kinds': ['call', 'return'], 'event_stride': .5},
           lesson='Function entry adds a fifth; returns add a fifth and octave. Call depth changes voice/register.')
    record('array_changes', source('array_changes'), expected=[1,4,5],
           profile={**SEMANTIC, 'event_kinds': ['output'], 'ranges': {'*': [0,7]}, 'event_stride': 1},
           lesson='Three printed array states are arpeggiated in index order: unsorted, intermediate, sorted.')
    for name, expected, error in [('assertion_pass', 10, None), ('assertion_error', None, 'AssertionError')]:
        record(name, source('assertion'), inputs=fixture(name), expected=expected, error=error,
               profile={**SEMANTIC, 'event_kinds': ['branch', 'error'], 'event_stride': .5},
               lesson='A failed assertion is followed by an error cluster at semitone offsets 0, 1, and 6.')
    for name, expected in [('range_inside', 5), ('range_above', 15), ('range_below', -5)]:
        record(name, source('range'), inputs=fixture(name), expected=expected,
               profile={**SEMANTIC, 'event_kinds': ['declare'], 'variables': ['level'],
                        'ranges': {'level': [0,10]}, 'event_stride': 1},
               lesson='The declared integer uses [0,10]; outside values clamp to a boundary and add a chromatic cue.')
    record('watch_all', source('watch'), expected=6, lesson='All events from an accumulator with unrelated changing state.')
    record('watch_total', source('watch'), expected=6,
           profile={**SEMANTIC, 'variables': ['total'], 'event_kinds': ['declare','assign']},
           lesson='Only declarations/assignments of total; original event IDs and silent time gaps remain.')
    for mapping in ('semantic', 'legacy'):
        for variant, filename in [('original','sum_compact'), ('formatted','sum_formatted')]:
            record(f'{mapping}_{variant}', source(filename), expected=15,
                   profile={'version': 1, 'mapping': mapping},
                   lesson='Same algorithm and values; comments and line wrapping differ.')
        left, right = f'{mapping}_original', f'{mapping}_formatted'
        manifest['comparisons'][f'{mapping}_formatting'] = {
            'same_behavior': compare_traces(runs[left]['result']['trace'], runs[right]['result']['trace'])['equal'],
            'same_symbolic_performance': performance(runs[left]['notes']) == performance(runs[right]['notes']),
            'same_wav': (output/left/'execution.wav').read_bytes() == (output/right/'execution.wav').read_bytes(),
        }
    record('score_original', source('sum_compact'), expected=15, lesson='Executable score before editing the exclusive loop bound.')
    tokens, _ = code_score(parse(source('sum_compact')))
    position = tokens.index('..') + 1
    before = tokens[position]
    assert before == '6'
    tokens[position] = '7'
    edited = edit_score({'tokens': tokens, 'profile': SEMANTIC})
    record('score_edited', edited['source'], expected=21, lesson='The score editor changes token 6 to 7, regenerates notes/checksum, and executes the result.')
    decoded = execute(import_program(output/'score_edited'/'code.mid'))
    manifest['score_edit'] = {'token_index': position, 'old_token': before, 'new_token': tokens[position],
                              'decoded_return_value': decoded['return_value'], 'score_editor_return_value': edited['result']['return_value']}
    bundle = load_source(root/'examples'/'modules'/'main.son')
    record('module_bundle', bundle, expected=55, lesson='Local modules are bundled before independent evaluation and executable MIDI compilation.')
    independent = verify(bundle)
    assert independent['passed']
    save(output/'module_bundle'/'independent-verification.json', independent)
    record('off_by_one', source('off_by_one'), expected=10, lesson='One fewer loop iteration than score_original; result 10 instead of 15.')
    difference = compare_traces(runs['score_original']['result']['trace'], runs['off_by_one']['result']['trace'])
    difference['left_clip'], difference['right_clip'] = 'score_original', 'off_by_one'
    beat = difference['first_divergence'] * .25
    difference['suggested_loop_beats'] = [max(0, beat-.5), beat+1.25]
    manifest['comparisons']['off_by_one'] = difference
    save(output/'manifest.json', manifest)
    inventory = [f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}'
                 for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS']
    (output/'SHA256SUMS').write_text('\n'.join(inventory)+'\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'audio'/'v1')
    args = parser.parse_args()
    manifest = generate(args.output)
    print(f'Generated {len(manifest["clips"])} verified listening clips in {args.output}')


if __name__ == '__main__':
    main()
