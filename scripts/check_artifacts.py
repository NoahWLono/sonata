"""Re-read durable artifacts, verify invariants and create a checksum inventory."""
import hashlib
import json
from pathlib import Path
import wave

import numpy as np
from sonata.codec import import_program
from sonata.language import canonical, parse
from sonata.midi import read_midi
from sonata.runtime import execute, Limits
from sonata.validation import audit_correspondence

ROOT = Path(__file__).resolve().parents[1]


def main():
    count = 0
    for directory in sorted((ROOT / "audio" / "demos").iterdir()):
        source = (ROOT / "examples" / f"{directory.name}.son").read_text()
        result = json.loads((directory / "trace.json").read_text())
        notes = json.loads((directory / "notes.json").read_text())
        assert all(audit_correspondence(source,result["trace"],notes).values()), directory
        restored = import_program(directory / "code.mid")
        assert canonical(restored) == canonical(parse(source)), directory
        fixture = ROOT / "examples" / f"{directory.name}.json"
        inputs = json.loads(fixture.read_text()) if fixture.is_file() else None
        playback = execute(restored,Limits(max_depth=12), inputs=inputs)
        assert playback["return_value"] == result["return_value"]
        assert len(read_midi(directory / "execution.mid")) == len(notes)
        with wave.open(str(directory / "execution.wav")) as wav:
            frames,rate = wav.getnframes(),wav.getframerate()
            samples = np.frombuffer(wav.readframes(frames),dtype="<i2").astype(float)
            assert np.mean(samples*samples) > 0
            assert abs(frames/rate-(max(n["start"]+n["duration"] for n in notes)*.5+.2)) < 2/rate
        count += 1
    inventory = []
    for folder in ("audio","experiments/results","research/participant","research/researcher_only"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                inventory.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT)}")
    (ROOT / "audio" / "SHA256SUMS").write_text("\n".join(inventory)+"\n")
    print(f"Verified {count} real program artifact bundles; inventoried {len(inventory)} files.")


if __name__ == "__main__":
    main()
