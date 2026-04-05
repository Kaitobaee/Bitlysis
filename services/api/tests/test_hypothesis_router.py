"""POST /v1/jobs/.../hypothesis-suggestions — fallback khi không key; mock OpenRouter khi có key."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def _write_job_meta(upload_dir: Path, job_id: str, columns: list[str]) -> None:
    meta = {
        "job_id": job_id,
        "status": "uploaded",
        "stored_as": f"{job_id}.csv",
        "original_filename": "t.csv",
        "columns": columns,
        "size_bytes": 10,
        "row_preview_count": 5,
        "uploaded_at": "2024-01-01T00:00:00+00:00",
    }
    (upload_dir / f"{job_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )


def test_hypothesis_unknown_job_returns_404(tmp_path: Path) -> None:
    custom = Settings(upload_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: custom
    try:
        with TestClient(app) as client:
            r = client.post("/v1/jobs/does-not-exist/hypothesis-suggestions", json={})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_hypothesis_empty_columns_returns_400(tmp_path: Path) -> None:
    custom = Settings(upload_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: custom
    jid = "44444444-4444-4444-4444-444444444444"
    _write_job_meta(tmp_path, jid, [])
    try:
        with TestClient(app) as client:
            r = client.post(f"/v1/jobs/{jid}/hypothesis-suggestions", json={})
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_hypothesis_suggestions_no_api_key_uses_disabled(tmp_path: Path) -> None:
    custom = Settings(
        upload_dir=tmp_path,
        max_upload_bytes=2 * 1024 * 1024,
        api_cors_origins="http://test",
        openrouter_api_key=None,
        llm_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: custom
    jid = "11111111-1111-1111-1111-111111111111"
    _write_job_meta(tmp_path, jid, ["age", "group"])
    try:
        with TestClient(app) as client:
            r = client.post(f"/v1/jobs/{jid}/hypothesis-suggestions", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "disabled_no_key"
        assert len(body["result"]["hypotheses"]) >= 1
        assert body["result"]["hypotheses"][0]["hypothesis_id"].startswith("H_rule")
    finally:
        app.dependency_overrides.clear()


def test_hypothesis_suggestions_force_fallback(tmp_path: Path) -> None:
    custom = Settings(
        upload_dir=tmp_path,
        openrouter_api_key="sk-fake-would-not-be-called",
        llm_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: custom
    jid = "22222222-2222-2222-2222-222222222222"
    _write_job_meta(tmp_path, jid, ["x", "y"])
    try:
        with TestClient(app) as client:
            r = client.post(
                f"/v1/jobs/{jid}/hypothesis-suggestions",
                json={"force_fallback": True},
            )
        assert r.status_code == 200
        assert r.json()["source"] == "fallback"
        assert r.json()["warning"] is None
    finally:
        app.dependency_overrides.clear()


def test_hypothesis_suggestions_openrouter_mock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = (
        '{"schema_version":1,"hypotheses":['
        '{"hypothesis_id":"API_M1","statement_vi":"Mock","variables_involved":["x"],'
        '"suggested_test_kind":"timeseries"}]}'
    )

    def fake_call(_settings: Settings, *, user_prompt: str, client=None):  # noqa: ARG001
        return payload, "mock/model-id"

    monkeypatch.setattr(
        "app.services.llm_hypotheses.call_openrouter_chat",
        fake_call,
    )
    custom = Settings(
        upload_dir=tmp_path,
        openrouter_api_key="sk-test",
        llm_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: custom
    jid = "33333333-3333-3333-3333-333333333333"
    _write_job_meta(tmp_path, jid, ["x"])
    try:
        with TestClient(app) as client:
            r = client.post(f"/v1/jobs/{jid}/hypothesis-suggestions", json={})
        assert r.status_code == 200
        b = r.json()
        assert b["source"] == "openrouter"
        assert b["model"] == "mock/model-id"
        assert b["result"]["hypotheses"][0]["hypothesis_id"] == "API_M1"
    finally:
        app.dependency_overrides.clear()
