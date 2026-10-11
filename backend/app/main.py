"""FastAPI application entrypoint.

Startup (FastAPI lifespan — runs once, before serving):
    1. bootstrap config (env + SSM Parameter Store secrets)
    2. create the DB engine + connection pool
    3. bind S3 / SNS / OCR clients
    4. pull the fine-tuned model weights from S3
       (falls back to the rule-based classifier on failure)

Error-handling policy:
    * AI pipeline failure  -> generic 500, real error logged
      with a stack trace (never leaked to the client)
    * DB failure           -> 503 after internal retries
    * SNS / S3 side effects -> logged, never block a verdict
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.ai import AIPipelineError
from app.api import api_router
from app.core.config import bootstrap, get_settings
from app.db.session import dispose_db, init_db
from app.logging_config import setup_logging
from app.services import alerts, model_loader, ocr, storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    config = bootstrap()
    app.state.config = config

    init_db(config)
    storage.init_storage(config)
    alerts.init_alerts(config)
    ocr.init_ocr(config)
    model_loader.download_model_if_needed(config)

    logger.info(
        "startup complete",
        extra={
            "event": "startup",
            "environment": config.environment,
            "alert_threshold": config.alert_threshold,
            "alert_window_minutes": config.alert_window_minutes,
            "s3_configured": bool(config.s3_bucket),
            "sns_configured": bool(config.sns_topic_arn),
        },
    )
    yield
    dispose_db()


app = FastAPI(
    title="Scam Shield API",
    description="Backend for the Scam Shield scam-intelligence platform.",
    version="0.2.0",
    lifespan=lifespan,
)

# In production the browser talks to the same origin (ALB), so CORS stays
# narrow; for local dev the Vite dev server on :5173 needs it.
# CORS origins are non-secret config, so they are read from
# env/.env at import time (SSM only carries secrets).
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_as_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_oversized_payloads(request: Request, call_next):
    """Enforce the configured payload cap before the body is read."""
    length = request.headers.get("content-length")
    if length and length.isdigit():
        config = getattr(request.app.state, "config", None)
        limit = config.max_payload_bytes if config else 2 * 1024 * 1024
        if int(length) > limit:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload exceeds {limit} bytes."},
            )
    return await call_next(request)


@app.exception_handler(AIPipelineError)
async def ai_pipeline_error_handler(request: Request, exc: AIPipelineError):
    """Model failures become a clean 500; the real cause was
    logged (with stack trace) by the adapter."""
    logger.error("unhandled AI pipeline error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Analysis failed. Please try again later."},
    )


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    """RDS in a private subnet can blip; retries already ran
    inside the repository layer."""
    logger.error("database operation failed", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please try again."},
    )


app.include_router(api_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"service": "Scam Shield API", "docs": "/docs"}
