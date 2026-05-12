from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import Settings, get_settings
from app.schemas.run import RunRequest, RunResponse
from app.services.psychometrics import ENGINE_ID, run_psychometrics

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

    parsed = run_psychometrics(df, payload.analyses, random_seed=payload.random_seed)
    parsed.setdefault("engine", ENGINE_ID)
    ok = bool(parsed.get("ok"))
    rc = 0 if ok else 1

    return RunResponse(
        ok=ok,
        engine=str(parsed.get("engine") or ENGINE_ID),
        r_returncode=rc,
        result=parsed,
        stderr=None,
    )
