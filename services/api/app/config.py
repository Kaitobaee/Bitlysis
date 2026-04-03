from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_cors_origins: str = "http://localhost:3000"

    upload_dir: Path = Field(default=Path("./data/uploads"))
    max_upload_bytes: int = Field(
        default=52_428_800,
        description="Max upload size in bytes (default ~50 MiB)",
    )

    retention_enabled: bool = Field(default=True, description="Bật sweep xóa job quá hạn")
    retention_hours: int = Field(default=168, ge=1, description="TTL upload (giờ)")
    retention_sweep_interval_seconds: int = Field(
        default=3600,
        ge=60,
        description="Khoảng cách chạy sweep (giây)",
    )

    upload_rate_limit_enabled: bool = Field(default=True)
    upload_rate_limit_max_requests: int = Field(
        default=60,
        ge=1,
        description="Số POST /v1/upload tối đa mỗi IP window",
    )
    upload_rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Sliding window (giây) cho rate limit upload",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


settings = Settings()


def get_settings() -> Settings:
    """Mặc định trả về singleton `settings`; override trong test qua `dependency_overrides`."""
    return settings
