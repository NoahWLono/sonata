"""Exercise v1 workflows through the actual HTTP boundary."""
import io
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from sonata.codec import decode_notes
from sonata.language import canonical, parse
from sonata.server import create_server


@pytest.fixture
def studio():
    server = create_server("return 15;", port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    worker.join()


def post(studio, route, body):
    request = Request(studio + route, json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    return urlopen(request, timeout=10)


def test_score_editor_roundtrip_and_regenerated_checksum(studio):
    with post(studio, "/api/score", {"tokens": ["return", "21", ";"]}) as response:
        score = json.load(response)
    assert score["result"]["return_value"] == 21
    assert score["code_tokens"] == ["return", "21", ";"]
    assert canonical(decode_notes(score["code_notes"])) == canonical(parse("return 21;"))
    linked = [n for n in score["code_notes"] if n.get("token") is not None]
    assert {n["token_index"] for n in linked} == {0, 1, 2}
    for note in linked:
        assert note["token"] == score["code_tokens"][note["token_index"]]


def test_comparison_contains_both_executions(studio):
    source = "let total=0; for i in 1..6 { total=total+i; } return total;"
    with post(studio, "/api/compare", {"left": {"source": source},
              "right": {"source": source.replace("1..6", "1..5")}}) as response:
        comparison = json.load(response)
    assert comparison["left"]["result"]["return_value"] == 15
    assert comparison["right"]["result"]["return_value"] == 10
    assert comparison["comparison"]["first_event_divergence"] is not None
    assert comparison["comparison"]["first_note_divergence"] is not None


def test_fixture_transport_retains_signed64(studio):
    with post(studio, "/api/run", {"source": "return input(0);",
              "inputs_json": "[9007199254740993]"}) as response:
        result = json.load(response)
    assert result["result"]["return_value"] == {"$int": "9007199254740993"}


def test_filtered_export_uses_same_profile(studio):
    body = {"source": "let x=1; x=x+2; return x;",
            "profile": {"version": 1, "mapping": "semantic", "event_kinds": ["return"]}}
    with post(studio, "/api/run", body) as response:
        result = json.load(response)
    events = {e["id"]: e for e in result["result"]["trace"]}
    assert result["notes"]
    assert all(events[n["event_id"]]["kind"] == "return" for n in result["notes"])
    import mido
    with post(studio, "/api/export/midi", body) as response:
        midi = mido.MidiFile(file=io.BytesIO(response.read()))
    assert sum(msg.type == "note_on" and msg.velocity > 0 for track in midi.tracks for msg in track) == len(result["notes"])


@pytest.mark.parametrize("route,body", [
    ("/api/score", {"tokens": ["return", "1;return", "2", ";"]}),
    ("/api/score", {"tokens": ["return", 1, ";"]}),
    ("/api/score", {"tokens": ["let", "=", ";"]}),
    ("/api/run", {"source": "return 1;", "inputs_json": "{}"}),
    ("/api/compare", {"left": [], "right": {"source": "return 1;"}}),
])
def test_invalid_editor_inputs_have_structured_errors(studio, route, body):
    with pytest.raises(HTTPError) as error:
        post(studio, route, body)
    assert error.value.code == 400
    assert json.load(error.value)["error"]
