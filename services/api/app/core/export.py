"""Export job orchestration, decoupled from FastAPI routes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.repositories import get_job_repository
from app.schemas.job import JobStatus
from app.services.export_renderers import render_matplotlib_series_png
from app.services.export_zip_builder import build_export_zip_bytes
from app.services.job_data import load_job_dataframe
from app.services.provenance import build_run_manifest
from app.storage import get_storage

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Base class for export orchestration errors."""


class ExportJobNotFoundError(ExportError):
    pass


class ExportFileNotFoundError(ExportError):
    pass


class ExportJobStateError(ExportError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class HeavyExportRequiresStartError(ExportError):
    threshold_bytes: int
    actual_bytes: int


@dataclass(frozen=True)
class ExportTooLargeError(ExportError):
    max_bytes: int


def export_zip_key(job_id: str) -> str:
    return f"{job_id}.export.zip"


async def mark_exporting(settings: Settings, job_id: str) -> None:
    repo = get_job_repository(settings)
    raw = await repo.get_job(job_id)
    if raw is None:
        raise ExportJobNotFoundError(job_id)
    st = str(raw.get("status", ""))
    if st == JobStatus.exporting.value:
        return
    if st != JobStatus.succeeded.value:
        raise ExportJobStateError(
            "Chỉ job đã analyze thành công (succeeded) mới bắt đầu export phase."
        )
    await repo.patch_job(
        job_id,
        {
            "status": JobStatus.exporting.value,
            "export_phase_started_at": datetime.now(UTC).isoformat(),
        },
    )


async def _load_base_manifest(
    settings: Settings,
    raw: dict[str, object],
    job_id: str,
) -> dict[str, object]:
    rel = raw.get("manifest_stored_as")
    if rel:
        try:
            content = await get_storage(settings).read_file(str(rel))
            parsed = json.loads(content.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
        except FileNotFoundError:
            pass
    ver = int(raw.get("profiling_engine_version", 1))
    return build_run_manifest(job_id, ver)


async def build_export_bytes(
    settings: Settings,
    job_id: str,
    *,
    enforce_heavy_gate: bool,
) -> bytes:
    repo = get_job_repository(settings)
    raw = await repo.get_job(job_id)
    if raw is None:
        raise ExportJobNotFoundError(job_id)
    st = str(raw.get("status", ""))
    if st not in {JobStatus.succeeded.value, JobStatus.exporting.value}:
        raise ExportJobStateError("Export cần job succeeded hoặc đang exporting (ZIP nặng).")

    df = await load_job_dataframe(settings, raw)
    base_manifest = await _load_base_manifest(settings, raw, job_id)
    zip_bytes = build_export_zip_bytes(settings, job_id, raw, df, base_manifest=base_manifest)
    n = len(zip_bytes)
    if n > settings.export_max_zip_bytes:
        raise ExportTooLargeError(settings.export_max_zip_bytes)
    export_phase_started = (
        st == JobStatus.exporting.value or bool(raw.get("export_phase_started_at"))
    )
    if (
        enforce_heavy_gate
        and n > settings.export_zip_heavy_threshold_bytes
        and not export_phase_started
    ):
        raise HeavyExportRequiresStartError(settings.export_zip_heavy_threshold_bytes, n)
    return zip_bytes


async def build_and_store_export(
    settings: Settings,
    job_id: str,
    *,
    enforce_heavy_gate: bool = False,
) -> bytes:
    repo = get_job_repository(settings)
    zip_bytes = await build_export_bytes(
        settings,
        job_id,
        enforce_heavy_gate=enforce_heavy_gate,
    )
    key = export_zip_key(job_id)
    await get_storage(settings).save_file(key, zip_bytes, content_type="application/zip")
    await repo.patch_job(
        job_id,
        {
            "status": JobStatus.succeeded.value,
            "export_stored_as": key,
            "export_size_bytes": len(zip_bytes),
        },
    )
    return zip_bytes


async def build_export_job(settings: Settings, job_id: str) -> None:
    try:
        await build_and_store_export(settings, job_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("export failed for %s", job_id)
        try:
            await get_job_repository(settings).patch_job(
                job_id,
                {
                    "status": JobStatus.failed.value,
                    "error": {"code": "export_failed", "message": str(e)},
                },
            )
        except FileNotFoundError:
            pass


async def read_stored_export(settings: Settings, job_id: str) -> bytes:
    raw = await get_job_repository(settings).get_job(job_id)
    if raw is None:
        raise ExportJobNotFoundError(job_id)
    rel = raw.get("export_stored_as")
    if not rel:
        raise ExportFileNotFoundError(job_id)
    try:
        return await get_storage(settings).read_file(str(rel))
    except FileNotFoundError as e:
        raise ExportFileNotFoundError(job_id) from e


async def render_matplotlib_preview_bytes(settings: Settings, job_id: str) -> bytes:
    raw = await get_job_repository(settings).get_job(job_id)
    if raw is None:
        raise ExportJobNotFoundError(job_id)
    df = await load_job_dataframe(settings, raw)
    with TemporaryDirectory() as td:
        out = Path(td) / f"{job_id}.matplotlib_preview.png"
        ok = render_matplotlib_series_png(df, out)
        if not ok or not out.is_file():
            raise ExportFileNotFoundError(job_id)
        return out.read_bytes()
