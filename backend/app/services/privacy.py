"""Privacy-preserving transformations for data stored by the API.

The AI pipeline receives the original submission so that entity extraction
and classification retain their full accuracy.  Only the copy written to
the database passes through this module.
"""

from __future__ import annotations

import re


REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_PHONE = "[REDACTED_PHONE]"
REDACTED_UPI = "[REDACTED_UPI]"
REDACTED_URL = "[REDACTED_URL]"

# URLs are replaced first so phone numbers or UPI-looking strings in a URL
# cannot be partially redacted and leave a misleading persisted value.
_URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>'\"]+", re.IGNORECASE)
_UPI_RE = re.compile(r"(?<![\w.+-])[\w.+-]{2,}@[\w-]+(?:\.[\w-]+)*(?![\w.-])", re.IGNORECASE)
_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()().-]{8,}\d)(?!\w)")


def redact_sensitive_text(text: str) -> str:
    """Return a safe-to-persist copy of arbitrary submitted text.

    The operation is deterministic and intentionally conservative: it only
    replaces common contact/payment identifiers and leaves surrounding scam
    language useful for audit and support.  It does not mutate the caller's
    string, which remains available to the AI analysis step.
    """

    redacted = _URL_RE.sub(REDACTED_URL, text)
    redacted = _EMAIL_RE.sub(REDACTED_EMAIL, redacted)
    redacted = _UPI_RE.sub(REDACTED_UPI, redacted)
    redacted = _PHONE_RE.sub(REDACTED_PHONE, redacted)
    return redacted
