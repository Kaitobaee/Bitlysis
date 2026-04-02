from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.upload import router as upload_router

app = FastAPI(title="Bitlysis API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "bitlysis-api"}


@app.get("/")
def root():
    return {"message": "Bitlysis API — see /docs"}
