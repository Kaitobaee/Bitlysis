from __future__ import annotations

import time
from io import BytesIO

import pandas as pd

from app.config import Settings, get_settings
from app.main import app


def _wait_for_status(client, job_id: str, expected: set[str]) -> dict:
    final = None
    for _ in range(300):
        data = client.get(f"/v1/jobs/{job_id}").json()
        final = data["status"]
        if final in expected:
            return data
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {expected}; last status={final}")


def test_full_auto_analysis_python_fallback(client):
    rows = []
    for i in range(24):
        grp = "A" if i % 2 == 0 else "B"
        region = "N" if i % 3 == 0 else "S"
        age = 20 + i
        score = 50 + i * 1.5
        rows.append(f"{grp},{region},{age},{score}")
    body = "grp,region,age,score\n" + "\n".join(rows)
    files = {"file": ("full.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    spec = {
        "kind": "full_auto_analysis",
        "prefer_r": False,
        "max_categorical_pairs": 4,
        "max_group_comparisons": 6,
    }
    r1 = client.post(f"/v1/jobs/{job_id}/analyze", json=spec)
    assert r1.status_code == 202

    data = _wait_for_status(client, job_id, {"succeeded", "failed"})
    assert data["status"] == "succeeded"
    summary = data["result_summary"]
    assert summary["engine"] == "auto_full_analysis"
    sections = summary["analysis_sections"]
    assert sections["overview"]["row_count"] == 24
    assert sections["categorical_associations"]
    assert sections["mixed_group_comparisons"]


def test_full_auto_analysis_prefers_r_when_available(client, monkeypatch):
    import app.services.auto_analysis as auto_analysis

    def fake_run_r_pipeline_json(settings, df, analyses):
        assert len(analyses) >= 1
        return (
            {
                "ok": True,
                "engine": "bitlysis_r_pipeline",
                "results": [
                    {
                        "type": "cronbach_alpha",
                        "ok": True,
                        "ran": True,
                        "skipped": False,
                        "raw_alpha": 0.91,
                        "std_alpha": 0.92,
                        "n": len(df),
                    }
                ],
            },
            "",
            0,
        )

    monkeypatch.setattr(auto_analysis, "run_r_pipeline_json", fake_run_r_pipeline_json)

    rows = []
    for i in range(18):
        rows.append(f"{1.0 + i * 0.1},{2.0 + i * 0.2},{3.0 + i * 0.3}")
    body = "x1,x2,x3\n" + "\n".join(rows)
    files = {"file": ("numeric.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    spec = {"kind": "full_auto_analysis", "prefer_r": True}
    r1 = client.post(f"/v1/jobs/{job_id}/analyze", json=spec)
    assert r1.status_code == 202

    data = _wait_for_status(client, job_id, {"succeeded", "failed"})
    assert data["status"] == "succeeded"
    summary = data["result_summary"]
    assert summary["engine"] == "auto_full_analysis_r"
    r_block = summary["analysis_sections"]["r_block"]
    assert r_block["available"] is True
    assert r_block["results"]
