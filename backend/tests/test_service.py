"""Verify the published API contract and behavior under load."""

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Event

from starlette.testclient import TestClient

server = import_module("backend.app.main")
PAYLOAD = {"files": [{"path": "entry.py", "content": "def main(): pass"}]}


def test_openapi_describes_upload_and_response_models():
    with TestClient(server.app) as client:
        schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    result = schema.json()
    paths = result["paths"]
    upload = paths["/api/upload"]["post"]
    upload_schema = upload["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert upload_schema["properties"]["files"]["items"]["format"] == "binary"
    assert paths["/api/analyze"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["anyOf"]
    assert "Diagram" in result["components"]["schemas"]


def test_validation_errors_do_not_echo_input():
    with TestClient(server.app) as client:
        response = client.post(
            "/api/analyze",
            json={"files": [{"path": "test.py", "content": {"test": "private-src"}}]},
        )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "files", 0, "content"]
    assert "private-src" not in response.text


def test_busy_analysis_rejects_work_and_reuses_the_released_slot(monkeypatch):
    monkeypatch.setenv("FLOWGEN_ANALYSIS_SLOTS", "1")
    entered = Event()
    release = Event()
    analyze = server.analyze_files

    def wait_to_analyze(payload):
        entered.set()
        if not release.wait(8):
            raise RuntimeError("Timed out waiting for concurrency test.")
        return analyze(payload)

    monkeypatch.setattr(server, "analyze_files", wait_to_analyze)
    with TestClient(server.app) as client, ThreadPoolExecutor() as pool:
        first = pool.submit(client.post, "/api/analyze", json=PAYLOAD)
        try:
            assert entered.wait(5)
            health = client.get("/api/health")
            assert health.status_code == 200
            busy = client.post("/api/analyze", json=PAYLOAD)
            assert busy.status_code == 503
            assert busy.headers["Retry-After"] == "2"
            upload_busy = client.post(
                "/api/upload", files={"files": ("entry.py", b"def main(): pass")}
            )
            assert upload_busy.status_code == 503
        finally:
            release.set()
        assert first.result().status_code == 200
        assert client.post("/api/analyze", json=PAYLOAD).status_code == 200
