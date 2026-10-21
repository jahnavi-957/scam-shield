"""Upload endpoint: presigned S3 URLs for direct screenshot upload."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import get_settings
from app.services import storage
from app.schemas.analysis import PresignedUploadRequest, PresignedUploadResponse
from app.schemas.errors import ERROR_RESPONSES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"], responses=ERROR_RESPONSES)


def get_config(request: Request):
    return getattr(request.app.state, "config", get_settings())


@router.get("/uploads/presigned-url", response_model=PresignedUploadResponse)
def presigned_upload_url(
    payload: Annotated[PresignedUploadRequest, Query()],
    config=Depends(get_config),
) -> PresignedUploadResponse:
    """Return a presigned PUT URL so the frontend uploads a
    screenshot DIRECTLY to S3 — image bytes never touch the
    EC2 instance. The URL is valid for `expires_in` seconds
    and is signed for exactly one key, one verb and one
    content type.

    The frontend must send the returned `content_type` as the
    PUT request's Content-Type header, then POST the returned
    `s3_key` to /analyze/screenshot.
    """
    if not config.s3_bucket:
        raise HTTPException(
            status_code=503,
            detail="S3 storage is not configured on this deployment.",
        )

    expires_in = payload.expires_in or config.presign_expiry_seconds
    # Both the request model and Settings cap this at five minutes. Keep the
    # runtime comparison here as defense in depth when RuntimeConfig is
    # supplied by a test or a custom bootstrapper.
    if expires_in > min(300, config.presign_expiry_seconds):
        raise HTTPException(
            status_code=422,
            detail="expires_in must not exceed the configured five-minute maximum",
        )
    key = storage.new_upload_key(payload.content_type)
    url = storage.create_presigned_put_url(
        key,
        content_type=payload.content_type,
        expires_in=expires_in,
    )
    logger.debug("presigned upload URL issued", extra={"s3_key": key})
    return PresignedUploadResponse(
        s3_key=key,
        url=url,
        content_type=payload.content_type,
        expires_in=expires_in,
    )
