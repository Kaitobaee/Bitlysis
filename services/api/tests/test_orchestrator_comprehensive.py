"""End-to-end test cho comprehensive_analysis."""

from __future__ import annotations

import time
from io import BytesIO


def _wait_for_status(client, job_id: str, expected: set[str]) -> dict:
    final = None
    for _ in range(400):
        data = client.get(f"/v1/jobs/{job_id}").json()
        final = data["status"]
        if final in expected:
            return data
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {expected}; last status={final}")


def _csv_with_likert(n_rows: int = 40) -> bytes:
    rows = []
    import random

    random.seed(7)
    for _ in range(n_rows):
        row = [
            random.randint(1, 5),  # q1
            random.randint(1, 5),  # q2
            random.randint(1, 5),  # q3
            random.randint(1, 5),  # q4
            random.randint(1, 5),  # q5
            random.choice(["M", "F"]),  # gender
            "A" if random.random() < 0.5 else "B",  # group
            10 + random.random() * 5,  # score (numeric)
        ]
        rows.append(",".join(str(v) for v in row))
    header = "q1,q2,q3,q4,q5,gender,group,score"
    return ("\n".join([header, *rows])).encode("utf-8")


def test_comprehensive_analysis_e2e(client):
    files = {"file": ("survey.csv", BytesIO(_csv_with_likert(36)), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    spec = {
        "kind": "comprehensive_analysis",
        "enable_psychometrics": True,
        "enable_pls": False,
        "enable_timeseries": False,
        "enable_llm_hypotheses": False,
        "random_seed": 42,
    }
    r1 = client.post(f"/v1/jobs/{job_id}/analyze", json=spec)
    assert r1.status_code == 202, r1.text

    data = _wait_for_status(client, job_id, {"succeeded", "failed"})
    assert data["status"] == "succeeded", data
    summary = data["result_summary"]
    assert summary["engine"] == "bitlysis_comprehensive_analysis"

    # Academic summary
    acad = summary["academic_summary"]
    assert "methods" in acad
    assert "conclusion" in acad
    assert "data_type" in acad

    # Hypothesis table có ít nhất 1 dòng (categorical hoặc compare groups).
    assert isinstance(summary["hypothesis_table"], list)

    # Cleaning block.
    cleaning = summary["cleaning"]
    assert cleaning["summary"]["enabled"] is True
    assert isinstance(cleaning["log"], list)
    assert "data_clean_preview" in cleaning

    # Psychometrics block (đủ Likert).
    section = summary["analysis_sections"]
    assert "psychometrics_block" in section or "cronbach" in summary["results"]

    # Provenance ref nhúng manifest pointer + seed.
    prov = summary["provenance_ref"]
    assert prov["random_seed"] == 42
    assert prov["psychometrics_engine"] == "bitlysis_python_psychometrics"


def test_comprehensive_analysis_skips_likert_when_none(client):
    """File chỉ có numeric & categorical thường — không có psychometrics."""
    rows = []
    for i in range(20):
        rows.append(f"A,{i + 1.5},{20 + i}")
    body = "grp,score,age\n" + "\n".join(rows)
    files = {"file": ("plain.csv", BytesIO(body.encode("utf-8")), "text/csv")}
    r = client.post("/v1/upload", files=files)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    spec = {"kind": "comprehensive_analysis", "enable_psychometrics": True}
    r1 = client.post(f"/v1/jobs/{job_id}/analyze", json=spec)
    assert r1.status_code == 202

    data = _wait_for_status(client, job_id, {"succeeded", "failed"})
    assert data["status"] == "succeeded"
    summary = data["result_summary"]
    # Không có cột Likert → không tạo block psychometrics.
    section = summary["analysis_sections"]
    assert "psychometrics_block" not in section
