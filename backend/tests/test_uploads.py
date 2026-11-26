from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from starlette.testclient import TestClient

from backend.app.main import MAX_REQUEST_BYTES, app
from backend.app.model import MAX_SOURCE_BYTES


@pytest.fixture
def client():
    with TestClient(app) as session:
        yield session


def archive(entries):
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as output:
        for path, value in entries.items():
            output.writestr(path, value)
    return stream.getvalue()


def test_root_and_health(client):
    page = client.get("/")
    assert page.status_code == 200 and "Code visualization" in page.text
    assert "object-src 'none'" in page.headers["content-security-policy"]
    assert client.get("/assets/app.js").status_code == 200
    health = client.get("/api/health")
    assert set(health.json()["languages"]) == {
        "python",
        "javascript",
        "typescript",
        "java",
        "c",
        "cpp",
    }
    assert health.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("compressed", [True, False])
def test_multi_file_and_zip_upload(client, compressed):
    files = {
        "demo/main.py": "import helper\n\ndef main():\n    helper.run()\n",
        "demo/helper.py": "def run():\n    return True\n",
        "demo/node_modules/vendor.js": "function skip() {}",
        "demo/README.md": "ignored",
    }
    parts = (
        [("files", ("demo.zip", archive(files)))]
        if compressed
        else [("files", (path, text)) for path, text in files.items()]
    )
    response = client.post("/api/upload", files=parts)
    assert response.status_code == 200, response.text
    parsed = response.json()
    assert [item["path"] for item in parsed["files"]] == ["helper.py", "main.py"]
    assert {node["label"] for node in parsed["graph"]["nodes"]} == {"Main", "Run"}


def test_upload_rejects_bad_zip_utf8_mixed_and_unsupported(client):
    for parts in [
        [("files", ("bad.zip", b"bad format"))],
        [("files", ("bad.py", b"\xff"))],
        [("files", ("mixed.zip", archive({"a.py": "x = 1"}))), ("files", ("b.py", b"x = 2"))],
        [("files", ("empty.txt", b"nothing"))],
    ]:
        response = client.post("/api/upload", files=parts)
        assert response.status_code == 400, response.text


@pytest.mark.parametrize("zipped", [False, True])
def test_size_is_bounded_for_source_and_zip_members(client, zipped):
    data = b"a" * (MAX_SOURCE_BYTES + 1)
    file = ("oversize.zip", archive({"a.py": data})) if zipped else ("a.py", data)
    response = client.post("/api/upload", files={"files": file})
    assert response.status_code == 413, response.text


def test_invalid_paths_duplicate_paths_and_unknown_symbol(client):
    first = {"path": "main.py", "content": "x = 1"}
    assert client.post("/api/analyze", json={"files": [first, first]}).status_code == 400
    assert (
        client.post("/api/analyze", json={"files": [first], "symbolId": "missing"}).status_code
        == 422
    )
    assert (
        client.post("/api/analyze", json={"files": [{**first, "path": "../main.py"}]}).status_code
        == 400
    )


def test_whole_request_body_is_bounded(client):
    response = client.post("/api/analyze", content=b"x" * (MAX_REQUEST_BYTES + 1))
    assert response.status_code == 413
