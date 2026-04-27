from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.schemas.job import JobDetail, JobError, JobStatus
from app.schemas.profiling import ProfilingSummary
from app.storage import get_storage
from app.storage.base import Storage


class JobRepository(ABC):
    @abstractmethod
    async def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Create a new job metadata record."""

    @abstractmethod
    async def update_status(
        self,
        job_id: str,
        status: str | JobStatus,
        *,
        error: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update status fields in a D1-compatible shape."""

    @abstractmethod
    async def patch_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Partially update job metadata."""

    @abstractmethod
    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return raw job metadata."""

    @abstractmethod
    async def get_job_detail(self, job_id: str) -> JobDetail | None:
        """Return API-facing job detail."""

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete metadata and known stored objects."""


class FileJobRepository(JobRepository):
    def __init__(self, settings: Settings, storage: Storage | None = None) -> None:
        self.settings = settings
        self.storage = storage or get_storage(settings)
        self.root = settings.upload_dir

    def _meta_path(self, job_id: str) -> Path:
        root = self.root.resolve()
        path = (root / f"{job_id}.meta.json").resolve()
        path.relative_to(root)
        return path

    async def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            msg = "job_id is required"
            raise ValueError(msg)
        key = f"{job_id}.meta.json"
        payload = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")
        await self.storage.save_file(key, payload, content_type="application/json")
        return job

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        try:
            payload = await self.storage.read_file(f"{job_id}.meta.json")
        except FileNotFoundError:
            return None
        return json.loads(payload.decode("utf-8"))

    async def patch_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        data = await self.get_job(job_id)
        if data is None:
            msg = f"Job meta not found: {job_id}"
            raise FileNotFoundError(msg)
        data.update(updates)
        data["status_updated_at"] = datetime.now(UTC).isoformat()
        await self.create_job(data)
        return data

    async def update_status(
        self,
        job_id: str,
        status: str | JobStatus,
        *,
        error: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {"status": str(status)}
        if error is not None:
            updates["error"] = error
        if result_summary is not None:
            updates["result_summary"] = result_summary
        return await self.patch_job(job_id, updates)

    async def get_job_detail(self, job_id: str) -> JobDetail | None:
        raw = await self.get_job(job_id)
        if raw is None:
            return None
        try:
            return raw_to_job_detail(raw)
        except (ValidationError, ValueError, TypeError):
            return None

    async def delete_job(self, job_id: str) -> bool:
        raw = await self.get_job(job_id)
        if raw is None:
            return False
        for key in (
            "stored_as",
            "manifest_stored_as",
            "export_stored_as",
            "matplotlib_preview_stored_as",
        ):
            name = raw.get(key)
            if name:
                await self.storage.delete(str(name))
        await self.storage.delete(f"{job_id}.meta.json")
        return True

    async def iter_jobs(self) -> list[dict[str, Any]]:
        """File-backed scan used by retention until D1 is introduced."""
        root = self.root
        if not await asyncio.to_thread(root.is_dir):
            return []

        def read_all() -> list[dict[str, Any]]:
            jobs: list[dict[str, Any]] = []
            for meta_file in root.glob("*.meta.json"):
                try:
                    jobs.append(json.loads(meta_file.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    meta_file.unlink(missing_ok=True)
            return jobs

        return await asyncio.to_thread(read_all)


def raw_to_job_detail(raw: dict[str, Any]) -> JobDetail:
    job_id = str(raw.get("job_id") or "").strip()
    if not job_id:
        msg = "Job meta missing job_id"
        raise ValueError(msg)
    err = raw.get("error")
    error_model = JobError(**err) if isinstance(err, dict) and "message" in err else None
    raw_status = str(raw.get("status", JobStatus.uploaded.value))
    try:
        status = JobStatus(raw_status)
    except ValueError:
        status = JobStatus.uploaded
    prof = None
    if isinstance(raw.get("profiling"), dict):
        try:
            prof = ProfilingSummary.model_validate(raw["profiling"])
        except ValidationError:
            prof = None
    a_spec = raw.get("analysis_spec")
    return JobDetail(
        job_id=job_id,
        status=status,
        filename=str(raw.get("original_filename", "")),
        stored_path=str(raw.get("stored_as", "")),
        size_bytes=int(raw.get("size_bytes", 0)),
        columns=list(raw.get("columns") or []),
        row_preview_count=int(raw.get("row_preview_count", 0)),
        uploaded_at=raw.get("uploaded_at"),
        status_updated_at=raw.get("status_updated_at"),
        error=error_model,
        result_summary=raw.get("result_summary"),
        profiling=prof,
        manifest_stored_as=raw.get("manifest_stored_as"),
        profiling_detail=raw.get("profiling_detail"),
        analysis_spec=a_spec if isinstance(a_spec, dict) else None,
        export_stored_as=raw.get("export_stored_as"),
    )


def get_job_repository(settings: Settings) -> JobRepository:
    return FileJobRepository(settings)
