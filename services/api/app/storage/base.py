from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredFile:
    key: str
    size_bytes: int
    content_type: str | None = None
    local_path: Path | None = None


class Storage(ABC):
    @abstractmethod
    async def save_file(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> StoredFile:
        """Persist bytes under a storage key and return metadata."""

    @abstractmethod
    async def read_file(self, key: str) -> bytes:
        """Read file content by storage key."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a stored object. Returns True when an object was removed."""

    async def generate_signed_url(
        self,
        key: str,
        *,
        expires_in_seconds: int = 3600,
    ) -> str | None:
        """Optional for backends that support direct object downloads."""
        return None
