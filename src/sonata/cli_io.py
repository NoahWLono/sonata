"""Bounded file loading and optional integration commands for the CLI."""
from importlib.resources import files
import json
from pathlib import Path


def read_json(path, maximum=1_048_576):
    with Path(path).open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"JSON file exceeds {maximum} bytes")
    return json.loads(data)


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def install_examples(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Example destination already exists; choose a new directory to preserve your files")
    resource = files("sonata").joinpath("examples")
    if not resource.is_dir():
        raise ValueError("Packaged examples are missing; reinstall the SONATA distribution")
    destination.mkdir(parents=True)

    def copy_directory(source, target):
        count = 0
        for entry in sorted(source.iterdir(), key=lambda p: p.name):
            if entry.is_dir():
                (target / entry.name).mkdir()
                count += copy_directory(entry, target / entry.name)
            else:
                (target / entry.name).write_bytes(entry.read_bytes())
                count += 1
        return count

    return {"directory": str(destination), "files": copy_directory(resource, destination)}


def midi_command(args):
    from .ports import list_ports, play_midi, capture_midi, replay_midi
    if args.midi_command == "ports":
        return list_ports()
    if args.midi_command == "inputs":
        from .ports import recording_inputs
        inputs = recording_inputs(read_json(args.file, maximum=16_777_216), max_notes=args.max_notes)
        save_json(args.output, inputs)
        return {"file": str(args.output), "notes": len(inputs[0]), "fields": ["pitches", "velocities", "times_us"]}
    if args.midi_command == "play":
        return play_midi(args.file, args.port, speed=args.speed)
    if args.midi_command == "record":
        recording = capture_midi(args.port, seconds=args.seconds)
        save_json(args.file, recording)
        return {"file": str(args.file), "messages": len(recording["messages"])}
    return replay_midi(read_json(args.file, maximum=16_777_216), args.port, speed=args.speed)
