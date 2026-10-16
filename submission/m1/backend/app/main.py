"""TaskBoard FastAPI entrypoint."""

from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import tasks

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)

# Exposes GET /metrics in Prometheus exposition format
Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/", tags=["meta"])
def root():
    return {"service": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health():
    """Liveness: is the process alive? Cheap, no DB touch."""
    return {"status": "UP"}


@app.get("/ready", tags=["meta"])
def ready(db: Session = Depends(get_db)):
    """Readiness: can we serve traffic? Verifies DB connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "READY"}
    except Exception as exc:  # pragma: no cover - exercised via integration
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "NOT_READY", "detail": str(exc)})
