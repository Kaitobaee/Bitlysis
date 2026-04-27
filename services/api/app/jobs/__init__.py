from __future__ import annotations

from fastapi import BackgroundTasks

from app.config import Settings
from app.jobs.cloudflare_queue_stub import CloudflareQueue
from app.jobs.local_queue import LocalQueue
from app.jobs.queue import Queue


def get_queue(
    settings: Settings,
    background_tasks: BackgroundTasks | None = None,
) -> Queue:
    if settings.queue_backend == "local":
        return LocalQueue(settings, background_tasks)
    if settings.queue_backend == "cloudflare":
        return CloudflareQueue()
    msg = f"Unsupported queue backend: {settings.queue_backend}"
    raise ValueError(msg)


__all__ = ["CloudflareQueue", "LocalQueue", "Queue", "get_queue"]
