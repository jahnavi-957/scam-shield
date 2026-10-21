"""OCR integration: extract text from an uploaded screenshot.

Default: Tesseract (pytesseract) running locally on the EC2
instance — the Docker image installs the ``tesseract-ocr`` apt
package, so there is no per-request AWS cost and no network hop.

Upgrade path: AWS Textract (serverless, better accuracy on noisy
screenshots, no local binary). Swapping engines is a one-function
change — both implement the same ``OCRProvider`` interface, and
``OCR_ENGINE=textract`` in config selects it. The interface is
deliberately tiny: bytes in, text out.
"""

from __future__ import annotations

import io
import logging
from typing import Protocol

import boto3
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

_provider = None
_config = None


class OCRProvider(Protocol):
    """Any engine that turns image bytes into text."""

    def extract_text(self, image_bytes: bytes) -> str: ...


class TesseractOCR:
    """Local Tesseract — the default. Runs in the container."""

    def extract_text(self, image_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image).strip()


class TextractOCR:
    """AWS Textract — the optional upgrade path."""

    def __init__(self, client=None):
        self._client = client or boto3.client("textract")

    def extract_text(self, image_bytes: bytes) -> str:
        response = self._client.detect_document_text(Document={"Bytes": image_bytes})
        return "\n".join(
            block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"
        ).strip()


def get_ocr_provider(config) -> OCRProvider:
    """Factory: config.ocr_engine selects the implementation."""
    if config.ocr_engine == "textract":
        return TextractOCR()
    return TesseractOCR()


def init_ocr(config) -> None:
    """Bind the OCR provider at startup."""
    global _provider, _config
    _config = config
    _provider = get_ocr_provider(config)


def extract_text_from_image(s3_key: str) -> str:
    """Fetch a screenshot from S3 and OCR it.

    Same interface for both engines — switching Tesseract for
    Textract is a config change, not a code change.
    """
    from app.services import storage  # local import: avoids a cycle at import time

    if _provider is None or _config is None:
        raise RuntimeError("OCR not initialised — init_ocr() runs at app startup")
    image_bytes = storage.fetch_object(s3_key, max_bytes=_config.max_image_bytes)
    storage.validate_image(image_bytes, _config)
    return _provider.extract_text(image_bytes)
