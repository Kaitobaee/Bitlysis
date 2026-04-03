"""Phase 2: magic-byte, DELETE job."""

from io import BytesIO


def test_xlsx_rejects_non_zip(client):
    files = {
        "file": (
            "fake.xlsx",
            BytesIO(b"not-a-zip-content"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 415
    assert r.json()["code"] == "http_415"


def test_csv_rejects_embedded_nul(client):
    files = {"file": ("bad.csv", BytesIO(b"a\x00,b\n1,2\n"), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 415


def test_delete_job_removes_files(client):
    body = "c,d\n3,4\n"
    files = {"file": ("d.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    job_id = r.json()["job_id"]
    d = client.delete(f"/v1/jobs/{job_id}")
    assert d.status_code == 204
    assert client.get(f"/v1/jobs/{job_id}").status_code == 404


def test_delete_unknown_job(client):
    assert (
        client.delete("/v1/jobs/00000000-0000-4000-8000-000000000099").status_code == 404
    )
