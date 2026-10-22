"""Analysis endpoints: POST /analyze/text and /analyze/screenshot."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.ai import AIPipelineError
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.analysis import (
    AnalyzeScreenshotRequest,
    AnalyzeTextRequest,
    AnalysisResponse,
)
from app.services.analysis import analyze_screenshot as run_screenshot_analysis
from app.services.analysis import analyze_text as run_text_analysis
from app.services import storage
from app.schemas.errors import ERROR_RESPONSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analysis"], responses=ERROR_RESPONSES)


def get_config(request: Request):
    """Runtime config, populated at startup (SSM + env)."""
    return getattr(request.app.state, "config", get_settings())


@router.post("/text", response_model=AnalysisResponse)
def analyze_text(
    payload: AnalyzeTextRequest,
    db: Session = Depends(get_db),
    config=Depends(get_config),
) -> AnalysisResponse:
    """Analyse a raw text message.

    Runs the AI pipeline, persists the verdict + embedding,
    tracks entity report counts, and fires the SNS alert when
    an entity crosses the configured threshold.
    """
    started = time.perf_counter()
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text must not be empty")
    if len(text) > config.max_text_length:
        raise HTTPException(status_code=422, detail="text exceeds the configured length limit")

    try:
        result = run_text_analysis(db, config, text)
    except AIPipelineError:
        # Already logged with a stack trace by the adapter;
        # the client gets a generic message, never the cause.
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Please try again later.",
        )

    logger.info(
        "analyze completed",
        extra={
            "event": "analyze",
            "source": "text",
            "is_scam": result["is_scam"],
            "scam_type": result["scam_type"],
            "confidence": round(result["confidence"], 3),
            "entity_count": len(result["entities"]),
            "prior_reports": result["prior_reports"],
            "alert_triggered": result["alert_triggered"],
            "duration_ms": round((time.perf_counter() - started) * 1000),
        },
    )
    return AnalysisResponse(**result)


@router.post("/screenshot", response_model=AnalysisResponse)
def analyze_screenshot(
    payload: AnalyzeScreenshotRequest,
    db: Session = Depends(get_db),
    config=Depends(get_config),
) -> AnalysisResponse:
    """Analyse a screenshot the frontend already uploaded to
    S3 via a presigned URL. OCR runs first, then the same
    pipeline as /analyze/text."""
    started = time.perf_counter()

    try:
        result = run_screenshot_analysis(db, config, payload.s3_key)
    except storage.ImageTooLargeError:
        raise HTTPException(
            status_code=413,
            detail="The screenshot exceeds the configured size limit.",
        )
    except storage.ImageValidationError:
        raise HTTPException(
            status_code=422,
            detail="The screenshot is not a valid supported image.",
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="The screenshot contains no readable text.",
        )
    except AIPipelineError:
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Please try again later.",
        )
    except OperationalError:
        # Preserve the global 503 database error contract. A database outage
        # is not a bad screenshot and must not be reported as a 502 OCR error.
        raise
    except Exception:
        # S3 fetch or OCR failure: the screenshot is the
        # input, so without it there is nothing to classify.
        logger.error(
            "screenshot fetch/OCR failed",
            extra={"event": "screenshot_error"},
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Could not process the screenshot.",
        )

    logger.info(
        "analyze completed",
        extra={
            "event": "analyze",
            "source": "screenshot",
            "is_scam": result["is_scam"],
            "scam_type": result["scam_type"],
            "confidence": round(result["confidence"], 3),
            "entity_count": len(result["entities"]),
            "prior_reports": result["prior_reports"],
            "alert_triggered": result["alert_triggered"],
            "duration_ms": round((time.perf_counter() - started) * 1000),
        },
    )
    return AnalysisResponse(**result)
