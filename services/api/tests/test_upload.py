from io import BytesIO

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_upload_csv_ok(client):
    body = "a,b\n1,2\n3,4\n"
    files = {"file": ("sample.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "uploaded"
    assert data["columns"] == ["a", "b"]
    assert data["row_preview_count"] == 2
    assert data["size_bytes"] == len(body.encode("utf-8"))
    assert data["stored_path"].endswith(".csv")


def test_upload_rejects_bad_extension(client):
    files = {"file": ("x.exe", BytesIO(b"abc"), "application/octet-stream")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 400
    payload = r.json()
    assert "request_id" in payload
    assert payload["code"] == "http_400"


def test_upload_too_large(tmp_path):
    custom = Settings(upload_dir=tmp_path, max_upload_bytes=10, api_cors_origins="http://test")
    app.dependency_overrides[get_settings] = lambda: custom
    try:
        with TestClient(app) as c:
            body = b"x" * 50
            files = {"file": ("big.csv", BytesIO(body), "text/csv")}
            r = c.post("/v1/upload", files=files)
            assert r.status_code == 413
            assert "request_id" in r.json()
    finally:
        app.dependency_overrides.clear()
