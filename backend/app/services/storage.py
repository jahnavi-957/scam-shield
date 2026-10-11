"""S3 integration: presigned upload URLs + object fetch.

Why presigned URLs (viva talking point): the frontend uploads
screenshots DIRECTLY to S3, so image bytes never route through
the small EC2 instance — that saves its memory and bandwidth,
removes a whole class of upload-timeout failures, and the URL is
a time-limited capability (default 15 minutes) for exactly one
object and one HTTP verb. The backend only ever handles the S3
key afterwards.

Key scheme: uploads/{uuid}.png — flat, unique, no user input in
the key, so keys are safe to log and impossible to collide.

Lifecycle note (Terraform's job, not implemented here): the
infra/ module should add an S3 lifecycle rule on the uploads/
prefix — transition to STANDARD_IA after 30 days, expire after
90 days. Screenshots are only needed until OCR completes; the
extracted text lives in RDS.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)

_s3 = None
_bucket: str = ""

# Content types we hand out presigned URLs for (screenshots only).
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}


def init_storage(config) -> None:
    """Create the S3 client and bind the bucket. Called at startup."""
    global _s3, _bucket
    _s3 = boto3.client("s3", region_name=config.aws_region)
    _bucket = config.s3_bucket


def new_upload_key(content_type: str = "image/png") -> str:
    """Generate a unique object key: uploads/{uuid}.{ext}."""
    ext = {
        "image/png": "png",
        "image/jpeg": "jpg",
    }.get(content_type, "png")
    return f"uploads/{uuid.uuid4().hex}.{ext}"


def create_presigned_put_url(
    key: str, *, content_type: str = "image/png", expires_in: int = 900
) -> str:
    """Presigned PUT URL so the frontend uploads straight to S3.

    The URL is signed for a specific Content-Type: the frontend
    MUST send that same Content-Type header with the PUT, otherwise
    S3 rejects the request (signature mismatch). The response model
    tells the frontend which content type to send.
    """
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    params = {"Bucket": _bucket, "Key": key, "ContentType": content_type}
    return _s3.generate_presigned_url(
        "put_object", Params=params, ExpiresIn=expires_in
    )


def fetch_object(key: str) -> bytes:
    """Download an object (e.g. an uploaded screenshot) for OCR."""
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    response = _s3.get_object(Bucket=_bucket, Key=key)
    return response["Body"].read()


def object_exists(key: str) -> bool:
    """Cheap existence check (used to validate screenshot keys)."""
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    try:
        _s3.head_object(Bucket=_bucket, Key=key)
        return True
    except _s3.exceptions.ClientError:
        return False
