import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_run():
    proc = subprocess.run([sys.executable, "-m", "sonata", "run", "examples/sum.son"], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["return_value"] == 15


def test_cli_syntax_error(tmp_path):
    source = tmp_path / "broken.son"
    source.write_text("let = ;")
    proc = subprocess.run([sys.executable, "-m", "sonata", "run", str(source)], text=True, capture_output=True)
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
