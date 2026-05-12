from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings, settings
from app.error_handlers import register_error_handlers
from app.logging_conf import configure_logging, log_event
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.upload_rate_limit import UploadRateLimitMiddleware
from app.routers.v1.export_router import router as v1_export_router
from app.routers.v1.hypotheses import router as v1_hypotheses_router
from app.routers.v1.jobs import router as v1_jobs_router
from app.routers.v1.run import router as v1_run_router
from app.routers.v1.upload import router as v1_upload_router
from app.routers.v1.web import router as v1_web_router
from app.services.retention import sweep_expired_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    cfg = get_settings()
    app.state.settings = cfg
    sweep_task: asyncio.Task[None] | None = None
    if cfg.retention_enabled and cfg.retention_sweep_interval_seconds > 0:
        sweep_task = asyncio.create_task(_retention_loop(cfg))
    yield
    if sweep_task is not None:
        sweep_task.cancel()
        with suppress(asyncio.CancelledError):
            await sweep_task


async def _retention_loop(cfg: Settings):
    log = logging.getLogger("bitlysis.retention")
    while True:
        await asyncio.sleep(cfg.retention_sweep_interval_seconds)
        try:
            n = await sweep_expired_jobs(cfg)
            log_event(log, "retention_sweep", deleted=n)
        except Exception:
            log.exception("retention_sweep_failed")


app = FastAPI(title="Bitlysis API", version="0.1.0", lifespan=lifespan)

register_error_handlers(app)

cfg = get_settings()
if cfg.trusted_hosts_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=cfg.trusted_hosts_list)
app.add_middleware(SecurityHeadersMiddleware, settings=cfg)
app.add_middleware(UploadRateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

v1 = APIRouter(prefix="/v1")
v1.include_router(v1_upload_router)
v1.include_router(v1_jobs_router)
v1.include_router(v1_hypotheses_router)
v1.include_router(v1_export_router)
v1.include_router(v1_web_router)
v1.include_router(v1_run_router)
app.include_router(v1)


@app.get("/health")
def health():
    return {"status": "ok", "service": "bitlysis-api"}


@app.get("/")
def root():
    return {"message": "Bitlysis API — see /docs", "v1": "/v1"}
