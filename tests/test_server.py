import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest
from sonata.server import create_server


@pytest.fixture
def server():
    http = create_server("let total = 0; for i in 1..6 { total = total + i; } return total;", "sum.son", 0)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http.server_port}"
    http.shutdown()
    http.server_close()
    thread.join()


def test_real_http_execution_and_exports(server):
    data = json.dumps({"source": "return 15;", "palette": "classical"}).encode()
    request = Request(server + "/api/run", data=data, headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        result = json.load(response)
    assert result["result"]["return_value"] == 15
    assert result["notes"] and result["code_notes"]
    for kind, magic in [("wav", b"RIFF"), ("midi", b"MThd"), ("code-midi", b"MThd")]:
        with urlopen(Request(server + "/api/export/" + kind, data=data, headers={"Content-Type": "application/json"})) as response:
            assert response.read().startswith(magic)


def test_foreign_origin_and_invalid_source_rejected(server):
    with pytest.raises(HTTPError) as error:
        urlopen(Request(server + "/api/run", data=b'{}', headers={"Content-Type": "application/json", "Origin": "https://foreign.test"}))
    assert error.value.code == 403
    with pytest.raises(HTTPError) as error:
        urlopen(Request(server + "/api/run", data=b'{"source":"let = ;"}', headers={"Content-Type": "application/json"}))
    assert error.value.code == 400


def test_large_integer_browser_transport_is_lossless(server):
    data = json.dumps({"source": "let x=9007199254740993; return x;"}).encode()
    with urlopen(Request(server+"/api/run",data=data,headers={"Content-Type":"application/json"})) as response:
        payload = json.load(response)
    assert payload["result"]["return_value"] == {"$int":"9007199254740993"}
