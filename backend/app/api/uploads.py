"""Upload endpoint: presigned S3 URLs for direct screenshot upload."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.services import storage
from app.schemas.analysis import PresignedUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])


def get_config(request: Request):
    return request.app.state.config


@router.get("/uploads/presigned-url", response_model=PresignedUploadResponse)
def presigned_upload_url(
    content_type: str = "image/png",
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
    if content_type not in storage.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"content_type must be one of {sorted(storage.ALLOWED_CONTENT_TYPES)}",
        )
    if not config.s3_bucket:
        raise HTTPException(
            status_code=503,
            detail="S3 storage is not configured on this deployment.",
        )

    key = storage.new_upload_key(content_type)
    url = storage.create_presigned_put_url(
        key,
        content_type=content_type,
        expires_in=config.presign_expiry_seconds,
    )
    logger.debug("presigned upload URL issued", extra={"s3_key": key})
    return PresignedUploadResponse(
        s3_key=key,
        url=url,
        content_type=content_type,
        expires_in=config.presign_expiry_seconds,
    )
