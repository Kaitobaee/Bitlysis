from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_upload_includes_profiling_and_manifest(client, tmp_path):
    body = "a,b\n1,2\n3,4\n"
    files = {"file": ("sample.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200
    data = r.json()
    assert "profiling" in data
    assert data["profiling"]["column_count"] == 2
    assert data["profiling"]["row_count_profiled"] == 2
    assert data["manifest_stored_as"].endswith(".manifest.json")
    job_id = data["job_id"]
    manifest = tmp_path / data["manifest_stored_as"]
    assert manifest.is_file()
    assert job_id in manifest.read_text(encoding="utf-8")


def test_get_job_includes_profiling_detail(client):
    body = "x,y\n10,20\n"
    files = {"file": ("t.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    job_id = r.json()["job_id"]
    g = client.get(f"/v1/jobs/{job_id}")
    assert g.status_code == 200
    j = g.json()
    assert j["profiling"]["column_count"] == 2
    assert j["profiling_detail"]["column_profiles"]
    for cp in j["profiling_detail"]["column_profiles"]:
        assert "missing_pct" in cp
        assert "nunique" in cp


def test_excel_profiling_lists_sheets(tmp_path):
    custom = Settings(
        upload_dir=tmp_path,
        max_upload_bytes=2_000_000,
        api_cors_origins="http://t",
        profiling_max_rows=500,
    )
    root = Path(__file__).resolve().parents[1]
    xlsx = root / "tests" / "fixtures" / "sample_multi_sheet_merged.xlsx"
    assert xlsx.is_file()
    app.dependency_overrides[get_settings] = lambda: custom
    try:
        with TestClient(app) as c:
            with xlsx.open("rb") as f:
                r = c.post(
                    "/v1/upload",
                    files={
                        "file": (
                            "m.xlsx",
                            f,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                    },
                )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    prof = r.json()["profiling"]
    assert prof["sheet_used"] == "Sales"
    assert prof["sheet_names"] and "Summary" in prof["sheet_names"]
