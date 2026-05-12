from __future__ import annotations

from app.storage.base import Storage, StoredFile


class R2Storage(Storage):
    def __init__(self, bucket_name: str | None) -> None:
        self.bucket_name = bucket_name

    async def save_file(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> StoredFile:
        # TODO(cloudflare): implement using an R2 binding/client in the container runtime.
        raise NotImplementedError("R2 storage backend is scaffolded but not implemented yet")

    async def read_file(self, key: str) -> bytes:
        # TODO(cloudflare): read object bytes from R2.
        raise NotImplementedError("R2 storage backend is scaffolded but not implemented yet")

    async def delete(self, key: str) -> bool:
        # TODO(cloudflare): delete object from R2.
        raise NotImplementedError("R2 storage backend is scaffolded but not implemented yet")

    async def generate_signed_url(
        self,
        key: str,
        *,
        expires_in_seconds: int = 3600,
    ) -> str | None:
        # TODO(cloudflare): return a signed R2 URL or public bucket URL when configured.
        raise NotImplementedError("R2 signed URLs are not implemented yet")
