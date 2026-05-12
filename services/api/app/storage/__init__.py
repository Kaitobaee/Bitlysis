from __future__ import annotations

from app.config import Settings
from app.storage.base import Storage
from app.storage.local import LocalStorage
from app.storage.r2 import R2Storage


def get_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.upload_dir)
    if settings.storage_backend == "r2":
        return R2Storage(settings.r2_bucket)
    msg = f"Unsupported storage backend: {settings.storage_backend}"
    raise ValueError(msg)
