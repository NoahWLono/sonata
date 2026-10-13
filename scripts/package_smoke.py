"""Install a distribution in a new venv and exercise it outside the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def smoke(archive):
    archive = Path(archive).resolve()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONUTF8"] = "1"
    with tempfile.TemporaryDirectory(prefix="sonata-install-") as directory:
        root = Path(directory)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        def run(*args):
            result = subprocess.run([str(python), *map(str, args)], cwd=root, env=env,
                                    text=True, capture_output=True, timeout=180)
            if result.returncode:
                raise RuntimeError(f"Installed-package command failed: {args}\n{result.stdout}\n{result.stderr}")
            return result.stdout

        run("-m", "pip", "install", "--disable-pip-version-check", str(archive))
        version = run("-m", "sonata", "--version").strip()
        assert version == "SONATA 1.0.0", version
        run("-m", "sonata", "examples", "--output", "lessons")
        result = json.loads(run("-m", "sonata", "run", "lessons/sum.son"))
        assert result["return_value"] == 15
        fixture = json.loads(run("-m", "sonata", "run", "lessons/fixtures.son", "--inputs", "lessons/fixtures.json"))
        assert fixture["return_value"] == 16
        modules = json.loads(run("-m", "sonata", "run", "lessons/modules/main.son"))
        assert modules["return_value"] == 55
        run("-m", "sonata", "compile", "lessons/sum.son", "--midi", "program.mid")
        run("-m", "sonata", "decode", "program.mid", "--output", "recovered.son")
        assert json.loads(run("-m", "sonata", "run", "recovered.son"))["return_value"] == 15
        run("-m", "sonata", "listen", "lessons/sum.son", "--semantic", "--wav", "performance.wav")
        assert (root / "performance.wav").read_bytes().startswith(b"RIFF")
        assert json.loads(run("-m", "sonata", "verify", "lessons/stdlib.son"))["passed"]
        run("lessons/integrations/compose.py", "composition")
        assert (root / "composition" / "composition.mid").is_file()
        assert len(json.loads((root / "composition" / "stems" / "manifest.json").read_text(encoding="utf-8"))["voices"]) == 3
        run("lessons/integrations/trace_python.py", "python-trace")
        assert json.loads((root / "python-trace" / "trace.json").read_text(encoding="utf-8"))["return_value"] == 5
        run("-m", "sonata", "midi", "inputs", "lessons/integrations/recording.json",
            "--output", "recorded-inputs.json")
        assert len(json.loads((root / "recorded-inputs.json").read_text(encoding="utf-8"))) == 3
        run("-c", "from importlib.resources import files; from sonata.server import create_server; "
            "assert files('sonata').joinpath('web','app.js').is_file(); "
            "assert files('sonata').joinpath('examples','sum.son').is_file(); "
            "server=create_server('return 1;',port=0); server.server_close()")
    return {"archive": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "passed": True, "version": version, "checks": ["isolated installation", "CLI",
            "packaged examples", "fixtures", "local modules", "MIDI roundtrip", "WAV",
            "independent verification", "composition and stems", "trusted Python trace",
            "recorded MIDI fixtures", "packaged web resources", "loopback server"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = [smoke(path) for path in args.archives]
    text = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
