from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002"

    # Phase 11–12 — hardening (để trống = tắt TrustedHost)
    api_trusted_hosts: str = Field(
        default="",
        description="Danh sách Host header (comma); production: api.example.com,*.onrender.com",
    )

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

    profiling_max_rows: int = Field(
        default=10_000,
        ge=50,
        le=500_000,
        description="Số dòng tối đa đọc cho profiling (cap bộ nhớ)",
    )

    r_subprocess_timeout_seconds: int = Field(
        default=180,
        ge=15,
        le=3600,
        description="Timeout Rscript Phase 5 (Cronbach/EFA/PLS)",
    )
    r_package_root: Path | None = Field(
        default=None,
        description="Thư mục packages/r-pipeline; mặc định suy ra từ repo",
    )
    bitlysis_rscript_path: Path | None = Field(
        default=None,
        description="Đường dẫn đầy đủ tới Rscript.exe nếu không có trên PATH",
    )
    run_endpoint_token: str | None = Field(
        default=None,
        description="Token bảo vệ POST /v1/run qua header X-Run-Token",
    )

    # Phase 7 — OpenRouter (ADR 0004)
    openrouter_api_key: str | None = Field(default=None, description="Bearer key; chỉ env")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL OpenRouter-compatible",
    )
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model id OpenRouter — eval golden không phụ thuộc biến này",
    )

    # Optional direct OpenAI provider support (fallback when OpenRouter key is absent)
    openai_api_key: str | None = Field(default=None, description="Direct OpenAI API key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible chat completions",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="Model id for direct OpenAI provider",
    )
    openrouter_http_referer: str = Field(
        default="https://github.com/bitlysis/bitlysis",
        description="HTTP-Referer header (OpenRouter khuyến nghị)",
    )
    openrouter_app_title: str = Field(default="Bitlysis API", description="X-Title header")
    openrouter_json_mode: bool = Field(
        default=True,
        description="Bật response_format json_object khi model hỗ trợ",
    )
    llm_enabled: bool = Field(default=True, description="Tắt để luôn rule-based")
    llm_timeout_seconds: float = Field(default=45.0, ge=5.0, le=120.0)
    llm_max_hypotheses: int = Field(default=10, ge=1, le=15)
    app_environment: Literal["development", "production", "test"] = Field(
        default="development",
        description="production: không log nội dung prompt (PII)",
    )
    llm_log_prompts: bool = Field(
        default=False,
        description="Chỉ bật local; kết hợp app_environment!=production mới log excerpt",
    )

    # Phase 8 — export ZIP
    export_zip_heavy_threshold_bytes: int = Field(
        default=5_242_880,
        ge=1,
        description="ZIP lớn hơn ngưỡng này chỉ khi job đã ở phase exporting (ge=1 cho test/CI)",
    )
    export_max_zip_bytes: int = Field(
        default=104_857_600,
        ge=1_048_576,
        description="Từ chối nếu ZIP vượt quá (bytes)",
    )
    export_data_max_rows: int = Field(
        default=100_000,
        ge=100,
        le=500_000,
        description="Giới hạn dòng sheet data_clean",
    )
    export_include_plotly: bool = Field(
        default=True,
        description="Thử Plotly→PNG (kaleido); tắt nếu CI không cài kaleido",
    )
    export_docx_template_path: Path | None = Field(
        default=None,
        description="Template .docx tùy chọn; None = tạo tài liệu mặc định",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.api_trusted_hosts.split(",") if h.strip()]


settings = Settings()


def get_settings() -> Settings:
    """Mặc định trả về singleton `settings`; override trong test qua `dependency_overrides`."""
    return settings
