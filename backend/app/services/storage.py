"""S3 integration: presigned upload URLs + object fetch.

Why presigned URLs (viva talking point): the frontend uploads
screenshots DIRECTLY to S3, so image bytes never route through
the small EC2 instance — that saves its memory and bandwidth,
removes a whole class of upload-timeout failures, and the URL is
a time-limited capability (default 5 minutes) for exactly one
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
import io
import warnings

import boto3
from botocore.config import Config as BotoConfig
from PIL import Image

logger = logging.getLogger(__name__)

_s3 = None
_presign_s3 = None
_bucket: str = ""
_public_endpoint_url: str = ""
_max_object_bytes: int = 10 * 1024 * 1024

# Content types we hand out presigned URLs for (screenshots only).
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}

# Default maximum file size for screenshot uploads (10 MB). The runtime
# setting is authoritative and can be smaller for constrained deployments.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ImageValidationError(ValueError):
    """The downloaded object is not an allowed, bounded screenshot."""


class ImageTooLargeError(ImageValidationError):
    """The object or image exceeds a configured byte limit."""


def create_s3_client(config, *, endpoint_override: str | None = None):
    """Build an AWS S3 or MinIO-compatible client from runtime settings."""
    kwargs: dict = {"region_name": config.aws_region}
    endpoint = endpoint_override or getattr(config, "s3_endpoint_url", "")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["config"] = BotoConfig(
            signature_version="s3v4",
            s3={
                "addressing_style": "path"
                if getattr(config, "s3_force_path_style", True)
                else "auto"
            },
        )
    credentials = {
        name: getattr(config, name, "")
        for name in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token")
    }
    if credentials["aws_access_key_id"] and credentials["aws_secret_access_key"]:
        kwargs.update({key: value for key, value in credentials.items() if value})
    return boto3.client("s3", **kwargs)


def init_storage(config) -> None:
    """Create the S3 client and bind the bucket. Called at startup.

    When ``s3_endpoint_url`` is set (e.g. MinIO for local dev) the
    client is pointed at that URL; otherwise it uses the default
    AWS S3 endpoint for the configured region.
    """
    global _s3, _presign_s3, _bucket, _public_endpoint_url, _max_object_bytes
    _s3 = create_s3_client(config)
    _bucket = config.s3_bucket
    _public_endpoint_url = getattr(config, "s3_public_endpoint_url", "").rstrip("/")
    _presign_s3 = (
        create_s3_client(config, endpoint_override=_public_endpoint_url)
        if _public_endpoint_url
        else _s3
    )
    _max_object_bytes = int(getattr(config, "max_image_bytes", MAX_UPLOAD_BYTES))


def new_upload_key(content_type: str = "image/png") -> str:
    """Generate a unique object key: uploads/{uuid}.{ext}."""
    ext = {
        "image/png": "png",
        "image/jpeg": "jpg",
    }.get(content_type, "png")
    return f"uploads/{uuid.uuid4().hex}.{ext}"


def create_presigned_put_url(
    key: str, *, content_type: str = "image/png", expires_in: int = 300
) -> str:
    """Presigned PUT URL so the frontend uploads straight to S3.

    The URL is signed for a specific Content-Type: the frontend
    MUST send that same Content-Type header with the PUT, otherwise
    S3 rejects the request (signature mismatch). The response model
    tells the frontend which content type to send.

    The object is still validated and bounded when the analysis endpoint
    downloads it. A PUT presigned URL cannot enforce a multipart POST
    content-length condition, so post-upload validation remains mandatory.
    """
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("unsupported image content type")
    if not 1 <= expires_in <= 300:
        raise ValueError("presigned URL expiry must be between 1 and 300 seconds")
    params = {"Bucket": _bucket, "Key": key, "ContentType": content_type}
    url = _presign_s3.generate_presigned_url(
        "put_object", Params=params, ExpiresIn=expires_in
    )
    return url


def fetch_object(key: str, *, max_bytes: int | None = None) -> bytes:
    """Download an object with a hard byte limit before OCR can see it."""
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    limit = int(_max_object_bytes if max_bytes is None else max_bytes)
    if limit < 1:
        raise ValueError("object download limit must be positive")
    response = _s3.get_object(Bucket=_bucket, Key=key)
    declared_length = response.get("ContentLength")
    if declared_length is not None and int(declared_length) > limit:
        response["Body"].close()
        raise ImageTooLargeError("image exceeds the configured size limit")

    body = response["Body"]
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = body.read(min(64 * 1024, limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise ImageTooLargeError("image exceeds the configured size limit")
            chunks.append(chunk)
    finally:
        body.close()
    return b"".join(chunks)


def validate_image(image_bytes: bytes, config=None) -> tuple[str, int, int]:
    """Validate image magic/content and dimensions with Pillow.

    File extensions and S3 Content-Type are untrusted metadata. Pillow must
    parse and verify the bytes, and dimensions/pixel count are bounded before
    an OCR engine receives the image.
    """
    if not image_bytes:
        raise ImageValidationError("image is empty")
    max_bytes = int(getattr(config, "max_image_bytes", _max_object_bytes))
    max_width = int(getattr(config, "max_image_width", 4096))
    max_height = int(getattr(config, "max_image_height", 4096))
    max_pixels = int(getattr(config, "max_image_pixels", 16_777_216))
    if len(image_bytes) > max_bytes:
        raise ImageTooLargeError("image exceeds the configured size limit")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as image:
                image_format = (image.format or "").upper()
                if image_format not in {"PNG", "JPEG"}:
                    raise ImageValidationError("only PNG and JPEG images are supported")
                width, height = image.size
                if width < 1 or height < 1 or width > max_width or height > max_height:
                    raise ImageValidationError("image dimensions exceed the configured limit")
                if width * height > max_pixels:
                    raise ImageValidationError("image pixel count exceeds the configured limit")
                image.verify()
                return image_format, width, height
    except ImageValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageValidationError("image dimensions are unsafe") from exc
    except Exception as exc:
        raise ImageValidationError("object is not a valid PNG or JPEG image") from exc


def object_exists(key: str) -> bool:
    """Cheap existence check (used to validate screenshot keys)."""
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    try:
        _s3.head_object(Bucket=_bucket, Key=key)
        return True
    except _s3.exceptions.ClientError:
        return False


def delete_object(key: str) -> None:
    """Delete a processed upload from the private bucket.

    The upload is temporary evidence for OCR, not the system of record. The
    caller treats deletion as best-effort and the bucket lifecycle rule is the
    recovery control if a worker/container dies before this runs.
    """
    if not _bucket:
        raise RuntimeError("S3 bucket is not configured")
    _s3.delete_object(Bucket=_bucket, Key=key)
