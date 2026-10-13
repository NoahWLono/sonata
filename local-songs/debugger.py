#!/usr/bin/env python3
"""Start the actual SONATA debugger with this machine's local song provider."""
import argparse
from pathlib import Path

from sonata.server import create_server
from debug_performances import LocalPerformances


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8977)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    source = "let total = 0;\nfor i in 1..6 {\n    total = total + i;\n}\nprint(total);\nreturn total;\n"
    server = create_server(source, "sum.son", port=args.port,
                           performance_provider=LocalPerformances(directory))
    print(f"SONATA debugger with local songs: http://127.0.0.1:{server.server_port}/", flush=True)
    print("Choose a score in Local songs, then press Play. Nothing is uploaded.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
