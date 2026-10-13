from pathlib import Path

import pytest

from sonata.codec import compile_program, import_program
from sonata.language import SonataSyntaxError, canonical, parse
from sonata.reference import evaluate
from sonata.runtime import execute


def write(root, name, source):
    path = root / (name + '.son')
    path.write_text(source, encoding='utf-8')
    return path


def test_nested_module_bundle_executes_roundtrips_and_has_honest_locations(tmp_path):
    from sonata.loader import load_program, load_source
    write(tmp_path, 'base', 'fn double(n) { return n * 2; }')
    write(tmp_path, 'helper', 'import base; fn answer(n) { return double(n) + 1; }')
    path = write(tmp_path, 'main', 'import helper; import base;\nreturn answer(input(0));')
    source = load_source(path)
    ast = load_program(path)
    assert 'import ' not in source
    assert source.count('fn double(') == 1
    assert ast == parse(source)
    result = execute(ast, inputs=[20])
    assert result['return_value'] == 41
    assert evaluate(source, inputs=[20])['return_value'] == 41
    lines = source.splitlines()
    assert all(1 <= event['line'] <= len(lines) for event in result['trace'])
    output = tmp_path / 'bundle.mid'
    compile_program(ast, output)
    restored = import_program(output)
    assert canonical(restored) == canonical(ast)
    assert execute(restored, inputs=[20])['return_value'] == 41
    assert load_source(path) == source


def test_no_import_retains_original_source_and_locations(tmp_path):
    from sonata.loader import load_program, load_source
    source = '// heading\n\nreturn 2;'
    path = write(tmp_path, 'main', source)
    assert load_source(path) == source
    assert load_program(path) == parse(source)


@pytest.mark.parametrize(('main', 'helper', 'message'), [
    ('import helper;', 'print(1);', 'functions and imports'),
    ('import helper;', 'let x = 1;', 'functions and imports'),
    ('import helper;', 'import main;', 'cycle'),
    ('import helper; fn f() {}', 'fn f() {}', 'Duplicate function'),
    ('import helper;', 'fn abs() {}', 'reserved'),
])
def test_bad_modules_fail_before_any_execution(tmp_path, main, helper, message):
    from sonata.loader import SonataImportError, load_program
    path = write(tmp_path, 'main', main)
    write(tmp_path, 'helper', helper)
    with pytest.raises(SonataImportError, match=message):
        load_program(path)


def test_missing_import_and_symlink_escape_are_rejected(tmp_path):
    from sonata.loader import SonataImportError, load_program
    root = tmp_path / 'project'
    root.mkdir()
    path = write(root, 'main', 'import secret;')
    with pytest.raises(SonataImportError, match='Cannot read'):
        load_program(path)
    outside = write(tmp_path, 'secret', 'fn secret() { return 8; }')
    (root / 'secret.son').symlink_to(outside)
    with pytest.raises(SonataImportError, match='outside'):
        load_program(path)


@pytest.mark.parametrize('source', ['import ../secret;', 'import /secret;', 'import "secret";', 'if (true) { import helper; }', 'fn f() { import helper; }'])
def test_import_syntax_has_no_host_path_or_nested_import(source):
    with pytest.raises(SonataSyntaxError):
        parse(source)


def test_unresolved_import_is_structured_error_before_output():
    source = 'print(1); import helper;'
    result = execute(parse(source))
    assert result['error']['kind'] == 'ImportError'
    assert result['output'] == []
    assert evaluate(source)['error']['kind'] == 'ImportError'


def test_module_count_limit(tmp_path):
    from sonata.loader import SonataImportError, load_program
    for n in range(33):
        write(tmp_path, f'm{n}', f'import m{n+1};' if n < 32 else 'fn done() {}')
    with pytest.raises(SonataImportError, match='32'):
        load_program(tmp_path / 'm0.son')


def test_combined_source_limit_and_invalid_utf8(tmp_path):
    from sonata.loader import SonataImportError, load_program
    path = write(tmp_path, 'main', 'import helper;\n//' + 'x'*110000)
    write(tmp_path, 'helper', '//'+ 'y'*110000 + '\nfn f() {}')
    with pytest.raises(SonataImportError, match='200000'):
        load_program(path)
    path.write_bytes(b'\xff')
    with pytest.raises(SonataImportError, match='UTF-8'):
        load_program(path)
