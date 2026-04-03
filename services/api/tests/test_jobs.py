import time
from io import BytesIO

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_get_job_404(client):
    r = client.get("/v1/jobs/00000000-0000-4000-8000-000000000000")
    assert r.status_code == 404
    assert r.json()["request_id"]


def test_analyze_lifecycle(client):
    body = "x,y\n1,2\n"
    files = {"file": ("t.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    r0 = client.get(f"/v1/jobs/{job_id}")
    assert r0.status_code == 200
    assert r0.json()["status"] == "uploaded"

    r1 = client.post(f"/v1/jobs/{job_id}/analyze")
    assert r1.status_code == 202
    assert r1.json()["status"] == "analyzing"

    final = None
    for _ in range(200):
        g = client.get(f"/v1/jobs/{job_id}")
        assert g.status_code == 200
        final = g.json()["status"]
        if final == "succeeded":
            break
        time.sleep(0.01)
    assert final == "succeeded"
    data = client.get(f"/v1/jobs/{job_id}").json()
    assert data["result_summary"]["engine"] == "stub"


def test_analyze_conflict_when_not_uploaded(client, tmp_path):
    custom = Settings(upload_dir=tmp_path, max_upload_bytes=2_000_000, api_cors_origins="http://test")
    app.dependency_overrides[get_settings] = lambda: custom
    try:
        with TestClient(app) as c:
            body = "a\n1\n"
            r = c.post("/v1/upload", files={"file": ("a.csv", BytesIO(body.encode()), "text/csv")})
            job_id = r.json()["job_id"]
            c.post(f"/v1/jobs/{job_id}/analyze")
            r2 = c.post(f"/v1/jobs/{job_id}/analyze")
            assert r2.status_code == 409
    finally:
        app.dependency_overrides.clear()
