from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import Settings, get_settings
from app.schemas.run import RunRequest, RunResponse
from app.services.r_pipeline import run_r_pipeline_json

router = APIRouter(tags=["run"])


@router.post("/run", response_model=RunResponse)
def run_core_engine(
    payload: RunRequest,
    settings: Settings = Depends(get_settings),
    x_run_token: str | None = Header(default=None),
) -> RunResponse:
    required_token = (settings.run_endpoint_token or "").strip()
    if required_token and x_run_token != required_token:
        raise HTTPException(status_code=401, detail="Unauthorized run token")

    try:
        df = pd.DataFrame(payload.records)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid records payload: {e}") from e
    if df.empty:
        raise HTTPException(status_code=400, detail="records must not be empty")

    parsed, stderr, rc = run_r_pipeline_json(settings, df, payload.analyses)
    ok = bool(parsed.get("ok")) and rc == 0

    return RunResponse(
        ok=ok,
        r_returncode=rc,
        result=parsed if isinstance(parsed, dict) else {"ok": False, "error": "Invalid R output"},
        stderr=(stderr or "")[:8000] or None,
    )
