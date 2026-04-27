from __future__ import annotations

from typing import Any

from fastapi import BackgroundTasks

from app.config import Settings
from app.core.analysis import run_analysis_job
from app.core.export import build_export_job
from app.jobs.queue import JobAction, Queue


class LocalQueue(Queue):
    def __init__(self, settings: Settings, background_tasks: BackgroundTasks | None = None) -> None:
        self.settings = settings
        self.background_tasks = background_tasks

    async def enqueue(
        self,
        job_id: str,
        action: JobAction,
        payload: dict[str, Any] | None = None,
    ) -> None:
        payload = payload or {}
        if action == "analyze":
            spec = payload.get("spec")
            if not isinstance(spec, dict):
                msg = "Local analyze jobs require a spec payload"
                raise ValueError(msg)
            if self.background_tasks is not None:
                self.background_tasks.add_task(run_analysis_job, self.settings, job_id, spec)
                return
            await run_analysis_job(self.settings, job_id, spec)
            return

        if action == "export":
            if self.background_tasks is not None:
                self.background_tasks.add_task(build_export_job, self.settings, job_id)
                return
            await build_export_job(self.settings, job_id)
            return

        msg = f"Unsupported local queue action: {action}"
        raise ValueError(msg)
