"""Bounded, deterministic source-module bundling for locally selected programs.

Modules share one function namespace. Imports can name only sibling .son files;
imported files contain functions and imports, never executable top-level code.
A bundle is reparsed so trace locations refer to the source actually displayed.
"""
from pathlib import Path

from .language import format_source, parse, validate_ast
from .runtime import BUILTINS

MAX_MODULES = 32
MAX_SOURCE_CHARACTERS = 200_000
MAX_SOURCE_BYTES = MAX_SOURCE_CHARACTERS * 4


class SonataImportError(ValueError):
    """A module graph could not be safely and unambiguously bundled."""


def load_source(path: str | Path) -> str:
    """Read a program and return original text, or canonical bundled source.

    The selected entry's resolved parent is the import root. Every dependency
    must resolve inside that directory. There are no search paths, package
    downloads, host imports, namespaced aliases, or module initialization code.
    """
    entry = Path(path).resolve()
    root = entry.parent
    active, completed = set(), set()
    ordered, definitions = [], set()
    total_characters = 0
    entry_source = None
    had_import = False

    def visit(candidate, is_entry=False):
        nonlocal total_characters, entry_source, had_import
        target = candidate.resolve()
        if target.parent != root:
            raise SonataImportError(f"Module {candidate.name!r} resolves outside the selected program directory")
        if target in active:
            raise SonataImportError(f"Import cycle involving {candidate.name!r}")
        if target in completed:
            return
        if len(completed) + len(active) >= MAX_MODULES:
            raise SonataImportError("A program may load at most 32 source modules including its entry")
        try:
            with target.open('rb') as handle:
                data = handle.read(MAX_SOURCE_BYTES + 1)
        except OSError as failure:
            raise SonataImportError(f"Cannot read module {candidate.name!r}: {failure.strerror}") from None
        if len(data) > MAX_SOURCE_BYTES:
            raise SonataImportError("Module graph exceeds the 200000-character source budget")
        try:
            source = data.decode('utf-8')
        except UnicodeDecodeError:
            raise SonataImportError(f"Module {candidate.name!r} is not valid UTF-8") from None
        total_characters += len(source)
        if total_characters > MAX_SOURCE_CHARACTERS:
            raise SonataImportError("Module graph exceeds the 200000-character source budget")
        ast = parse(source)
        if is_entry:
            entry_source = source
        elif any(node['kind'] not in {'fn', 'import'} for node in ast['body']):
            raise SonataImportError(f"Imported module {candidate.name!r} may contain only functions and imports")
        active.add(target)
        for node in ast['body']:
            if node['kind'] == 'import':
                had_import = True
                visit(root / (node['name'] + '.son'))
        for node in ast['body']:
            if node['kind'] == 'import':
                continue
            if node['kind'] == 'fn':
                name = node['name']
                if name in definitions:
                    raise SonataImportError(f"Duplicate function {name!r} in module graph")
                if name in BUILTINS:
                    raise SonataImportError(f"Function {name!r} is reserved for a builtin")
                definitions.add(name)
            ordered.append(node)
        active.remove(target)
        completed.add(target)

    visit(entry, True)
    if not had_import:
        return entry_source
    bundle = {'kind': 'program', 'line': 1, 'col': 1, 'body': ordered}
    validate_ast(bundle)
    result = format_source(bundle)
    # Parsing also enforces the canonical output's size and AST bounds. The
    # result intentionally has fresh line numbers, never misleading originals.
    parse(result)
    return result


def load_program(path: str | Path) -> dict:
    """Parse the exact source returned by :func:`load_source`."""
    return parse(load_source(path))
