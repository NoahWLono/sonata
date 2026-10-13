"""Keep the distribution's examples identical to the repository originals."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".son", ".json", ".py", ".md"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source, target = ROOT / "examples", ROOT / "src/sonata/examples"
    originals = {p.relative_to(source): p.read_bytes() for p in source.rglob("*")
                 if p.is_file() and p.suffix in EXTENSIONS and "__pycache__" not in p.parts}
    existing = {p.relative_to(target) for p in target.rglob("*") if p.is_file()}
    stale = existing - originals.keys()
    changed = [name for name, data in originals.items()
               if not (target / name).is_file() or (target / name).read_bytes() != data]
    if args.check:
        if stale or changed:
            raise SystemExit("Packaged examples differ: run python scripts/sync_examples.py")
    else:
        for name in stale:
            (target / name).unlink()
        for name in changed:
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            (target / name).write_bytes(originals[name])
    print(f"Verified {len(originals)} packaged example resources")


if __name__ == "__main__":
    main()
