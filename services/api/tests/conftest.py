import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
def client(tmp_path):
    custom = Settings(
        upload_dir=tmp_path,
        max_upload_bytes=2 * 1024 * 1024,
        api_cors_origins="http://test",
        # Tắt rate limit trong test để tránh 429 giả
        testing=True,
        upload_rate_limit_enabled=False,
        analyze_rate_limit_enabled=False,
    )
    app.dependency_overrides[get_settings] = lambda: custom
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
