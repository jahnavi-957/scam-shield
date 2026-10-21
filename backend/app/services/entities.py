"""Canonical entity value normalization shared by extraction and lookup."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


ENTITY_TYPES = {"upi", "phone", "url"}
_PHONE_CHARS_RE = re.compile(r"[^\d+]")
_PHONE_RE = re.compile(r"^\+?\d{8,15}$")


def normalize_phone(value: str) -> str:
    """Normalize common Indian and international phone representations.

    Ten-digit local numbers are treated as Indian numbers because the
    extractor and the product currently target India.  Existing E.164 values
    remain intact, while spaces, punctuation and a leading ``00`` are
    canonicalized.
    """

    compact = _PHONE_CHARS_RE.sub("", value.strip())
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if compact.startswith("+"):
        digits = compact[1:]
    else:
        digits = compact

    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    elif len(digits) == 12 and digits.startswith("91"):
        pass

    normalized = "+" + digits
    if not _PHONE_RE.fullmatch(normalized):
        raise ValueError("invalid phone entity")
    return normalized


def normalize_url(value: str) -> str:
    """Normalize URL scheme/host casing and remove fragments."""

    raw = value.strip()
    if not raw:
        raise ValueError("empty URL entity")
    candidate = raw if "://" in raw else f"https://{raw}"
    parsed = urlsplit(candidate)
    if not parsed.hostname:
        raise ValueError("invalid URL entity")

    hostname = parsed.hostname.lower()
    netloc = hostname
    if parsed.port is not None:
        default_port = (parsed.scheme.lower() == "http" and parsed.port == 80) or (
            parsed.scheme.lower() == "https" and parsed.port == 443
        )
        if not default_port:
            netloc = f"{hostname}:{parsed.port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


def normalize_entity_value(entity_type: str, value: str) -> str:
    """Return the canonical storage/query representation for an entity."""

    entity_type = entity_type.strip().lower()
    if entity_type not in ENTITY_TYPES:
        raise ValueError("unsupported entity type")
    raw = value.strip()
    if not raw:
        raise ValueError("empty entity value")
    if entity_type == "phone":
        return normalize_phone(raw)
    if entity_type == "url":
        return normalize_url(raw)
    return re.sub(r"\s+", "", raw).lower()


def infer_entity_type(value: str) -> str | None:
    """Infer the lookup type for a value when the caller omits it."""

    raw = value.strip()
    if "@" in raw:
        return "upi"
    try:
        normalize_phone(raw)
    except ValueError:
        pass
    else:
        return "phone"

    if "://" in raw or raw.lower().startswith(("www.", "http.")) or "." in raw:
        try:
            normalize_url(raw)
        except ValueError:
            pass
        else:
            return "url"
    return None
