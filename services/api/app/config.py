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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


settings = Settings()


def get_settings() -> Settings:
    """Mặc định trả về singleton `settings`; override trong test qua `dependency_overrides`."""
    return settings
