from __future__ import annotations

from typing import Any

from app.jobs.queue import JobAction, Queue


class CloudflareQueue(Queue):
    async def enqueue(
        self,
        job_id: str,
        action: JobAction,
        payload: dict[str, Any] | None = None,
    ) -> None:
        # TODO(cloudflare): publish {job_id, action, payload} to a Cloudflare Queue.
        raise NotImplementedError("Cloudflare Queue backend is scaffolded but not implemented yet")
