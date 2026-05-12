from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

JobAction = Literal["analyze", "export"]


class Queue(ABC):
    @abstractmethod
    async def enqueue(
        self,
        job_id: str,
        action: JobAction,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue background work for the selected action."""
