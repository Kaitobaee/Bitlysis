from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.config import Settings, get_settings
from app.schemas.job import AnalyzeAccepted, JobDetail, JobStatus
from app.schemas.stats import AnalyzeRequest
from app.services import job_store
from app.services.analyze_tasks import run_analyze

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> JobDetail:
    detail = job_store.get_job_detail(settings, job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    return detail


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
