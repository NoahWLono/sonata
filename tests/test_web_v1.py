"""Browser state regressions with DOM/audio stubs; actual browser checks are separate."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_browser_v1_state_machine():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is optional; browser state harness requires Node")
    subprocess.run([node, str(ROOT / "tests/browser_v1.cjs")], cwd=ROOT, check=True)
