"""The installed distribution must contain the documented offline resources."""
from importlib.resources import files
from pathlib import Path
import subprocess
import sys


def test_packaged_examples_match_sources():
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / "scripts/sync_examples.py"), "--check"], check=True)
    assert files("sonata").joinpath("web", "index.html").is_file()
    assert files("sonata").joinpath("examples", "modules", "main.son").is_file()
