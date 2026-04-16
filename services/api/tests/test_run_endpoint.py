from __future__ import annotations

from app.config import get_settings
from app.main import app
from app.config import Settings


def test_run_endpoint_requires_token_when_configured(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        api_cors_origins="http://test",
        run_endpoint_token="secret-token",
    )

    payload = {
        "records": [{"x1": 1, "x2": 2}],
        "analyses": [{"type": "cronbach_alpha", "scale_id": "s", "items": ["x1", "x2"]}],
    }
    r = client.post("/v1/run", json=payload)
    assert r.status_code == 401
    app.dependency_overrides.clear()


def test_run_endpoint_executes_r_pipeline(client, monkeypatch):
    def fake_run_r_pipeline_json(settings, df, analyses):  # noqa: ANN001
        assert list(df.columns) == ["x1", "x2"]
        assert analyses[0]["type"] == "cronbach_alpha"
        return ({"ok": True, "results": [{"type": "cronbach_alpha", "ok": True}]}, "", 0)

    monkeypatch.setattr("app.routers.v1.run.run_r_pipeline_json", fake_run_r_pipeline_json)

    payload = {
        "records": [{"x1": 1, "x2": 2}, {"x1": 2, "x2": 3}],
        "analyses": [{"type": "cronbach_alpha", "scale_id": "s", "items": ["x1", "x2"]}],
    }
    r = client.post("/v1/run", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["r_returncode"] == 0
    assert data["result"]["ok"] is True
