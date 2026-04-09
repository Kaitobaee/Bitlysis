from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

import pandas as pd

from app.config import Settings, get_settings
from app.schemas.job import AnalyzeAccepted, JobDetail, JobStatus
from app.schemas.stats import AnalyzeRequest
from app.services import job_store
from app.services.analyze_tasks import run_analyze
from app.services.job_data import load_job_dataframe

router = APIRouter(tags=["jobs"])


def _column_chart_payload(
    df: pd.DataFrame,
    column: str,
    chart_type: str,
    max_items: int,
) -> dict[str, object]:
    if column not in df.columns:
        raise ValueError("Cột không tồn tại trong dữ liệu")

    s = df[column].dropna()
    if s.empty:
        raise ValueError("Cột không có dữ liệu hợp lệ")

    if pd.api.types.is_numeric_dtype(s):
        s_num = pd.to_numeric(s, errors="coerce").dropna()
        if s_num.empty:
            raise ValueError("Không thể đọc dữ liệu số từ cột")
        if int(s_num.nunique()) > max_items:
            bins = min(10, max(4, int(s_num.nunique() ** 0.5)))
            binned = pd.cut(s_num.astype(float), bins=bins, duplicates="drop")
            counts = binned.value_counts().sort_index()
            labels = [str(idx) for idx in counts.index]
            values = [int(v) for v in counts.values]
        else:
            counts = s_num.round(2).astype(str).value_counts().head(max_items)
            labels = [str(idx) for idx in counts.index]
            values = [int(v) for v in counts.values]
    else:
        counts = s.astype(str).value_counts().head(max_items)
        labels = [str(idx) for idx in counts.index]
        values = [int(v) for v in counts.values]

    return {
        "kind": chart_type,
        "title": f"{chart_type.upper()} - {column}",
        "column": column,
        "labels": labels,
        "values": values,
        "total": int(sum(values)),
    }


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> JobDetail:
    detail = job_store.get_job_detail(settings, job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return detail


@router.get("/jobs/{job_id}/charts/quick")
def get_quick_chart(
    job_id: str,
    column: str = Query(..., min_length=1),
    chart_type: str = Query("bar", pattern="^(bar|pie|line|area|donut)$"),
    max_items: int = Query(12, ge=3, le=30),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    try:
        df = load_job_dataframe(settings, raw)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Không đọc được dữ liệu job: {e}") from e

    try:
        return _column_chart_payload(df, column, chart_type, max_items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/jobs/{job_id}/analyze",
    status_code=202,
    response_model=AnalyzeAccepted,
)
async def start_analyze(
    job_id: str,
    background_tasks: BackgroundTasks,
    spec: AnalyzeRequest,
    settings: Settings = Depends(get_settings),
) -> AnalyzeAccepted:
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    st = str(raw.get("status", ""))
    allowed = {JobStatus.uploaded.value, JobStatus.failed.value}
    if st not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Job không thể chạy analyze ở trạng thái: {st}",
        )
    spec_dump = spec.model_dump(mode="json")
    job_store.patch_meta(
        settings,
        job_id,
        {
            "status": JobStatus.analyzing.value,
            "error": None,
            "analysis_spec": spec_dump,
        },
    )
    background_tasks.add_task(run_analyze, settings, job_id, spec_dump)
    return AnalyzeAccepted(job_id=job_id, status=JobStatus.analyzing)


@router.delete("/jobs/{job_id}", status_code=204)
def remove_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> None:
    if not job_store.delete_job(settings, job_id):
        raise HTTPException(status_code=404, detail="Job không tồn tại")
