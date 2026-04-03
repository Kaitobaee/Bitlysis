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
    body = (
        "grp,val\n"
        + "\n".join(f"A,{1.0 + i * 0.1}" for i in range(15))
        + "\n"
        + "\n".join(f"B,{2.5 + i * 0.1}" for i in range(15))
    )
    files = {"file": ("t.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    r0 = client.get(f"/v1/jobs/{job_id}")
    assert r0.status_code == 200
    assert r0.json()["status"] == "uploaded"

    spec = {
        "kind": "compare_groups_numeric",
        "outcome": "val",
        "group": "grp",
    }
    r1 = client.post(f"/v1/jobs/{job_id}/analyze", json=spec)
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
    assert data["result_summary"]["engine"] == "python_stats"
    assert data["result_summary"]["hypothesis_table"]
    assert data["result_summary"]["decision_trace"]["selected_method"]


def test_analyze_conflict_when_not_uploaded(client, tmp_path):
    custom = Settings(upload_dir=tmp_path, max_upload_bytes=2_000_000, api_cors_origins="http://test")
    app.dependency_overrides[get_settings] = lambda: custom
    try:
        with TestClient(app) as c:
            a_rows = [f"A,{1.0 + i * 0.05}" for i in range(12)]
            b_rows = [f"B,{2.0 + i * 0.05}" for i in range(12)]
            rows = a_rows + b_rows
            body = "g,v\n" + "\n".join(rows)
            r = c.post("/v1/upload", files={"file": ("a.csv", BytesIO(body.encode()), "text/csv")})
            job_id = r.json()["job_id"]
            spec = {"kind": "compare_groups_numeric", "outcome": "v", "group": "g"}
            r1 = c.post(f"/v1/jobs/{job_id}/analyze", json=spec)
            assert r1.status_code == 202
            final = None
            for _ in range(300):
                final = c.get(f"/v1/jobs/{job_id}").json()["status"]
                if final == "succeeded":
                    break
                time.sleep(0.01)
            assert final == "succeeded"
            r2 = c.post(f"/v1/jobs/{job_id}/analyze", json=spec)
            assert r2.status_code == 409
    finally:
        app.dependency_overrides.clear()
