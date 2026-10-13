import json
from pathlib import Path
import subprocess
import sys


def cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "sonata", *map(str, args)],
                          cwd=cwd, text=True, capture_output=True, timeout=20)


def test_cli_version_and_bundled_examples(tmp_path):
    version = cli("--version")
    assert version.returncode == 0
    assert "1.0.0" in version.stdout
    target = tmp_path / "lessons"
    install = cli("examples", "--output", target)
    assert install.returncode == 0, install.stderr
    assert (target / "sum.son").is_file()
    run = cli("run", target / "sum.son", cwd=tmp_path)
    assert json.loads(run.stdout)["return_value"] == 15
    again = cli("examples", "--output", target)
    assert again.returncode == 1  # User edits must not be overwritten.


def test_fixture_and_independent_verification(tmp_path):
    source, inputs = tmp_path / "test.son", tmp_path / "inputs.json"
    source.write_text("let x=input(0); assert(x>0); return x*2;")
    inputs.write_text("[7]")
    run = cli("run", source, "--inputs", inputs)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["return_value"] == 14
    verification = cli("verify", source, "--inputs", inputs)
    assert verification.returncode == 0, verification.stderr
    assert json.loads(verification.stdout)["passed"]


def test_compare_cli_and_recordings(tmp_path):
    left, right = tmp_path / "a.son", tmp_path / "b.son"
    left.write_text("let x=1; return x+1;")
    right.write_text("let x=1; return x+2;")
    result = cli("compare", left, right, "--wav-dir", tmp_path / "sounds")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["first_divergence"] is not None
    assert (tmp_path / "sounds" / "left.wav").read_bytes().startswith(b"RIFF")
    assert (tmp_path / "sounds" / "right.wav").read_bytes().startswith(b"RIFF")


def test_semantic_profile_and_stems(tmp_path):
    source = tmp_path / "simple.son"
    source.write_text("let x=1; return x+2;")
    wav = tmp_path / "out.wav"
    result = cli("listen", source, "--semantic", "--wav", wav, "--stems", tmp_path / "stems")
    assert result.returncode == 0, result.stderr
    assert wav.is_file()
    assert list((tmp_path / "stems").glob("*.mid"))


def test_bundle_modules_and_port_help(tmp_path):
    (tmp_path / "helpers.son").write_text("fn double(x){return x*2;}")
    source = tmp_path / "main.son"
    source.write_text("import helpers; return double(5);")
    bundled = tmp_path / "bundled.son"
    result = cli("bundle", source, "--output", bundled)
    assert result.returncode == 0, result.stderr
    assert "import" not in bundled.read_text()
    assert json.loads(cli("run", bundled).stdout)["return_value"] == 10
    assert cli("midi", "--help").returncode == 0


def test_invalid_json_and_profile_report_no_traceback(tmp_path):
    source, profile = tmp_path / "simple.son", tmp_path / "bad.json"
    source.write_text("return 1;")
    profile.write_text("[]")
    result = cli("listen", source, "--wav", tmp_path / "out.wav", "--profile", profile)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
