"""Loopback-only debugger with bounded requests and no arbitrary file serving."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
import tempfile
import webbrowser

from .studio import run_payload, edit_score, compare_payload
from .audio import render_wav
from .midi import write_midi

MAX_BODY = 65_536
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def browser_value(value):
    """Preserve semantic signed64 integers beyond JavaScript's exact range."""
    if type(value) is int and abs(value) > 2**53 - 1:
        return {"$int": str(value)}
    if isinstance(value, dict):
        return {key: browser_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [browser_value(item) for item in value]
    return value


def create_server(source, name="program.son", port=8765, inputs_json="[]", performance_provider=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, body, mime="application/json", filename=None):
            if isinstance(body, dict):
                body = json.dumps(browser_value(body)).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed:
                self.respond(403, {"error": "Debugger accepts only localhost requests"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + h for h in allowed}:
                self.respond(403, {"error": "Cross-origin requests are disabled"})
                return False
            return True

        def stream_asset(self, path, mime):
            """Serve one registered recording, including a single seek range."""
            with Path(path).open("rb") as stream:
                size = stream.seek(0, 2)
                first, last, status = 0, size - 1, 200
                requested = self.headers.get("Range")
                if requested is not None:
                    match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
                    valid = bool(match and any(match.groups()) and size)
                    if valid:
                        low, high = match.groups()
                        try:
                            if low:
                                first = int(low)
                                last = min(int(high), size - 1) if high else size - 1
                                valid = first < size and first <= last
                            else:
                                count = int(high)
                                first = max(0, size - count)
                                valid = count > 0
                        except ValueError:
                            valid = False
                    if not valid:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.send_header("Accept-Ranges", "bytes")
                        self.end_headers()
                        return
                    status = 206
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(max(0, last - first + 1)))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
                self.end_headers()
                stream.seek(first)
                remaining = last - first + 1
                try:
                    while remaining > 0:
                        chunk = stream.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # A media element can cancel a range when seeking.

        def performance_route(self):
            if self.path == "/api/performances":
                self.respond(200, {"performances": performance_provider.list() if performance_provider else []})
                return
            match = re.fullmatch(r"/api/performances/([A-Za-z0-9_-]+)(?:/(audio\.wav|performance\.mid))?", self.path)
            if performance_provider is None or not match:
                self.respond(404, {"error": "Unknown performance"})
                return
            identity, kind = match.groups()
            try:
                if kind is None:
                    self.respond(200, performance_provider.payload(identity))
                else:
                    self.stream_asset(performance_provider.asset(identity, kind),
                                      "audio/wav" if kind == "audio.wav" else "audio/midi")
            except (KeyError, FileNotFoundError):
                self.respond(404, {"error": "Unknown performance or missing recording"})
            except ValueError as exc:
                self.respond(409, {"error": str(exc)})

        def do_GET(self):
            if not self.valid_host():
                return
            if self.path == "/api/performances" or self.path.startswith("/api/performances/"):
                self.performance_route()
            elif self.path == "/api/default":
                self.respond(200, {"source": source, "name": name, "inputs_json": inputs_json})
            elif self.path == "/api/examples":
                directory = EXAMPLES if EXAMPLES.is_dir() else files("sonata").joinpath("examples")
                items = []
                for p in sorted(directory.iterdir(), key=lambda p: p.name):
                    if p.name.endswith(".son") and p.is_file():
                        fixture = directory.joinpath(p.name[:-4] + ".json")
                        items.append({"name": p.name, "source": p.read_text(encoding="utf-8"),
                                      "inputs_json": fixture.read_text(encoding="utf-8") if fixture.is_file() else "[]"})
                if not items:
                    items = [{"name": name, "source": source}]
                self.respond(200, {"examples": items})
            elif self.path in ("/", "/index.html", "/app.js", "/style.css"):
                filename = "index.html" if self.path == "/" else self.path[1:]
                path = files("sonata").joinpath("web", filename)
                if not path.is_file():
                    self.respond(404, {"error": "Debugger asset missing"})
                else:
                    mime = {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}[filename.rsplit(".",1)[1]]
                    self.respond(200, path.read_bytes(), mime)
            else:
                self.respond(404, {"error": "Unknown route"})

        def do_POST(self):
            if not self.valid_host():
                return
            if self.path not in ("/api/run", "/api/compare", "/api/score", "/api/export/wav", "/api/export/midi", "/api/export/code-midi"):
                self.respond(404, {"error": "Unknown route"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("Request must contain 1..65536 bytes")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected application/json")
                args = json.loads(self.rfile.read(length))
                if not isinstance(args, dict):
                    raise ValueError("Expected an object")
                if self.path == "/api/compare":
                    self.respond(200, compare_payload(args))
                    return
                if self.path == "/api/score":
                    self.respond(200, edit_score(args))
                    return
                payload = run_payload(args)
                if self.path == "/api/run":
                    self.respond(200, payload)
                    return
                notes, palette = payload["notes"], args.get("palette", "classical")
                kind = self.path.rsplit("/", 1)[1]
                with tempfile.TemporaryDirectory(prefix="sonata-export-") as directory:
                    suffix = "wav" if kind == "wav" else "mid"
                    path = Path(directory) / f"sonata.{suffix}"
                    if kind == "wav":
                        render_wav(notes, path, palette=palette)
                    elif kind == "midi":
                        write_midi(notes, path, palette=palette)
                    else:
                        write_midi(payload["code_notes"], path)
                    self.respond(200, path.read_bytes(), "audio/wav" if kind == "wav" else "audio/midi", f"sonata-{kind}.{suffix}")
            except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
                self.respond(400, {"error": str(exc)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve(path, port=8765, open_browser=False):
    inputs_json = "[]"
    if path is None:
        source, name = files("sonata").joinpath("examples", "sum.son").read_text(encoding="utf-8"), "sum.son"
    else:
        from .loader import load_source
        source, name = load_source(path), Path(path).name
        fixture = Path(path).with_suffix(".json")
        if fixture.is_file():
            with fixture.open(encoding="utf-8") as stream:
                inputs_json = stream.read(20_001)
            if len(inputs_json) > 20_000:
                raise ValueError("Default fixtures exceed 20000 characters")
    server = create_server(source, name, port, inputs_json=inputs_json)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"SONATA debugger: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
