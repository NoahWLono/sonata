"""Keep the user manual's code and ordered CLI walkthrough executable."""
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from sonata.codec import decode_notes, encode_ast
from sonata.language import canonical, parse
from sonata.loader import load_source
from sonata.reference import evaluate
from sonata.runtime import execute

ROOT = Path(__file__).resolve().parents[1]
DOCS = ('LANGUAGE_GUIDE.md', 'TUTORIAL.md')


def _blocks():
    result = []
    for name in DOCS:
        text = (ROOT / 'docs' / name).read_text(encoding='utf-8')
        snippets = re.findall(r'^```sonata\n(.*?)^```', text, re.MULTILINE | re.DOTALL)
        assert snippets, f'{name} must contain tested source examples'
        for number, snippet in enumerate(snippets, 1):
            result.append(pytest.param(snippet, id=f'{name}-{number}'))
    return result


def _metadata(source, key, fallback=None):
    match = re.search(r'^// ' + re.escape(key) + r': (.+)$', source, re.MULTILINE)
    return json.loads(match.group(1)) if match else fallback


@pytest.mark.parametrize('source', _blocks())
def test_manual_sonata_example(source):
    fixture_dir = _metadata(source, 'fixture-directory')
    if fixture_dir:
        # The manual shows the entry of an actual installed module example.
        bundled = load_source(ROOT / fixture_dir / 'main.son')
        entry = parse(source)
        actual_entry = parse((ROOT / fixture_dir / 'main.son').read_text())
        assert canonical(entry) == canonical(actual_entry)
        source = bundled + '\n// expected-return: 55\n'
    inputs = _metadata(source, 'inputs')
    ast = parse(source)
    restored = decode_notes(encode_ast(ast))
    assert canonical(restored) == canonical(ast)
    result = execute(ast, inputs=inputs)
    reference = evaluate(source, inputs=inputs)
    expected_error = _metadata(source, 'expected-error')
    if expected_error:
        assert result['error']['kind'] == expected_error
        assert reference['error']['kind'] == expected_error
    else:
        assert result['error'] is None, result
        assert reference['error'] is None, reference
        for field in ('return_value', 'output', 'globals'):
            assert result[field] == reference[field]
        assert result['return_value'] == _metadata(source, 'expected-return')
        assert execute(restored, inputs=inputs)['return_value'] == result['return_value']
    if re.search(r'^// expected-output:', source, re.MULTILINE):
        assert result['output'] == _metadata(source, 'expected-output')


def _cli(directory, *args):
    process = subprocess.run([sys.executable, '-m', 'sonata', *map(str, args)],
                             cwd=directory, capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, (args, process.stdout, process.stderr)
    return json.loads(process.stdout) if process.stdout.strip().startswith('{') else process.stdout


def test_tutorial_cli_walkthrough(tmp_path):
    _cli(tmp_path, 'examples', '--output', 'lessons')
    assert _cli(tmp_path, 'run', 'lessons/sum.son')['return_value'] == 15
    _cli(tmp_path, 'listen', 'lessons/sum.son', '--wav', 'sum.wav', '--midi', 'sum.runtime.mid', '--semantic')
    _cli(tmp_path, 'compile', 'lessons/sum.son', '--midi', 'sum.code.mid')
    _cli(tmp_path, 'decode', 'sum.code.mid', '--output', 'sum.decoded.son')
    assert _cli(tmp_path, 'run', 'sum.decoded.son')['return_value'] == 15
    assert _cli(tmp_path, 'verify', 'lessons/sum.son', '--report', 'verification.json')['passed']
    assert _cli(tmp_path, 'run', 'lessons/fixtures.son', '--inputs', 'lessons/fixtures.json')['return_value'] == 16
    _cli(tmp_path, 'bundle', 'lessons/modules/main.son', '--output', 'module.bundle.son')
    assert _cli(tmp_path, 'run', 'module.bundle.son')['return_value'] == 55
    _cli(tmp_path, 'compare', 'lessons/sum.son', 'lessons/off_by_one.son', '--report', 'comparison.json', '--wav-dir', 'comparison', '--semantic')
    assert (tmp_path / 'comparison/left.wav').is_file()
    assert (tmp_path / 'comparison/right.wav').is_file()
    assert (tmp_path / 'sum.wav').stat().st_size > 44
    same = _cli(tmp_path, 'compare', 'lessons/fixtures.son', 'lessons/fixtures.son',
                '--left-inputs', 'lessons/fixtures.json', '--right-inputs', 'lessons/fixtures.json',
                '--report', 'same-input.json')
    assert same['results'][0] == same['results'][1]
    _cli(tmp_path, 'listen', 'lessons/sum.son', '--wav', 'sum.ambient.wav', '--palette', 'ambient', '--semantic')
    assert (tmp_path / 'sum.ambient.wav').stat().st_size > 44
