from __future__ import annotations

import asyncio
from pathlib import Path

from app.storage.base import Storage, StoredFile


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path_for(self, key: str) -> Path:
        root = self.root.resolve()
        path = (root / key).resolve()
        path.relative_to(root)
        return path

    async def save_file(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> StoredFile:
        path = self._path_for(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(write)
        return StoredFile(
            key=key,
            size_bytes=len(content),
            content_type=content_type,
            local_path=path,
        )

    async def read_file(self, key: str) -> bytes:
        path = self._path_for(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> bool:
        path = self._path_for(key)
        if not await asyncio.to_thread(path.exists):
            return False
        await asyncio.to_thread(path.unlink)
        return True
