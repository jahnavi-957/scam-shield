"""Entity extraction for Indian-context scam messages.

Extracts four entity types from noisy real-world text (SMS, WhatsApp,
email bodies):

* Indian UPI IDs   ("name@bank", e.g. "fraud123@okaxis")
* Indian phone numbers (+91 / 0 / bare 10-digit mobile formats)
* URLs, including shortened links (bit.ly, tinyurl, t.co, ...)
* Monetary amounts ("Rs. 500", "INR 2000", "Rs.10 lakh")

Design decisions (for the viva):
- Regex-first, no ML dependency: extraction must be fast,
  deterministic and unit-testable; the classifier handles the fuzzy
  part of the problem.
- URLs and UPI IDs are MASKED before phone/amount extraction so a
  number embedded in a UPI ID ("9876543210@ybl") is never
  double-reported as a phone number.
- Input is Unicode-normalised (NFKC) and zero-width/bidi characters
  are stripped, so obfuscated scam text still parses.
- Results are deduplicated and order-preserving; malformed input
  (None, empty) yields empty lists instead of raising.
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- #
# UPI IDs
# --------------------------------------------------------------------------- #
# Local part: >=1 char, starts alphanumeric. Domain: >=3 chars, starts
# with a letter. Deliberately permissive — NPCI has hundreds of bank/PSP
# handles — so unknown handles still count; use `is_likely_upi_id` for a
# stricter check against well-known Indian handles.
UPI_ID_PATTERN = re.compile(r"\b[a-zA-Z0-9][a-zA-Z0-9._-]*@[a-zA-Z][a-zA-Z0-9]{2,}\b")

# Well-known Indian UPI handles (PSP + bank "ok*" handles). Non-exhaustive;
# used only for validation, never for extraction.
KNOWN_UPI_HANDLES = frozenset(
    {
        "ybl",  # PhonePe (Yes Bank)
        "paytm",
        "paytmmp",
        "axl",  # Amazon Pay (Axis)
        "upi",  # BHIM / NPCI
        "nbpi",
        "okaxis",
        "okhdfcbank",
        "okicici",
        "okbizaxis",
        "okbizhdfcbank",
        "okbizicici",
        "okyes",
        "okstatebank",
        "oksbi",
        "okkotak",
        "okunionbank",
        "okcanara",
        "okbankofbaroda",
        "okpnb",
        "hdfcbank",
        "icici",
        "axisbank",
        "sbi",
        "yesbank",
        "kotak",
    }
)


def is_likely_upi_id(candidate: str) -> bool:
    """Strict check: valid shape AND a recognised Indian UPI handle.

    Recognised = in KNOWN_UPI_HANDLES or an NPCI "ok*" bank handle.
    """
    if not candidate:
        return False
    text = candidate.strip()
    if not UPI_ID_PATTERN.fullmatch(text):
        return False
    handle = text.rsplit("@", 1)[1].lower()
    return handle in KNOWN_UPI_HANDLES or handle.startswith("ok")


# --------------------------------------------------------------------------- #
# Phone numbers (Indian mobiles: optional +91 / 91 / 0 prefix, then a
# 6-9 leading digit — the reserved mobile range — and 9 more digits,
# with an optional single space/dash inside the 5+5 split)
# --------------------------------------------------------------------------- #
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+91[\s-]?|91[\s-]?|0[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")


def _normalize_phone(raw: str) -> str:
    """Normalise any accepted Indian mobile format to +91XXXXXXXXXX."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return f"+91{digits}"


# --------------------------------------------------------------------------- #
# URLs (scheme + bare domains, incl. common shorteners)
# --------------------------------------------------------------------------- #
URL_SCHEME_PATTERN = re.compile(r"https?://[^\s<>\"']+")
URL_BARE_PATTERN = re.compile(
    r"(?<!\w)(?:[a-z0-9-]+\.)+(?:com|net|org|in|info|xyz|io|me|biz|cc|gd|ly|co)(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)


def _clean_url(url: str) -> str:
    """Strip trailing sentence punctuation that is not part of the URL."""
    return url.rstrip(".,;:!?)'\"")


# --------------------------------------------------------------------------- #
# Amounts (Rs / Rs. / RS / INR / Rupees / Rs-sign, Indian digit grouping,
# optional lakh/crore multiplier)
# --------------------------------------------------------------------------- #
AMOUNT_PATTERN = re.compile(
    r"(?:₹|Rs\.?|RS\.?|INR|Rupees)\s?(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore)?",
    re.IGNORECASE,
)


def _parse_amount(raw: str, multiplier: str | None) -> float:
    """Parse an Indian-formatted number; expand lakh/crore multipliers."""
    value = float(raw.replace(",", ""))
    if multiplier:
        value *= 1_00_000.0 if multiplier.lower() == "lakh" else 1_00_00_000.0
    return value


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
# Zero-width characters (U+200B-200F), bidi overrides (U+202A-202E)
# and word joiner (U+2060) — a common obfuscation trick in scam text.
_ZERO_WIDTH = re.compile("[​-‏‪-‮⁠]")


def _normalize_text(text: str | None) -> str:
    """NFKC-normalise and strip zero-width/bidi characters (obfuscation trick)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return text


def _dedupe(items: list[str]) -> list[str]:
    """Order-preserving deduplication."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _mask(text: str, matches: list[str]) -> str:
    """Replace each match with same-length NULs so later regexes skip it."""
    for match in matches:
        text = text.replace(match, "\x00" * len(match))
    return text


# --------------------------------------------------------------------------- #
# Public single-entity extractors (each normalises + masks internally,
# so they are safe to call standalone)
# --------------------------------------------------------------------------- #
def extract_upi_ids(text: str | None) -> list[str]:
    """Extract plausible Indian UPI IDs ('name@bank')."""
    clean = _normalize_text(text)
    clean = _mask(clean, extract_urls(clean))
    return _dedupe(UPI_ID_PATTERN.findall(clean))


def extract_phone_numbers(text: str | None) -> list[str]:
    """Extract Indian mobile numbers, normalised to +91XXXXXXXXXX."""
    clean = _normalize_text(text)
    clean = _mask(clean, extract_urls(clean))
    clean = _mask(clean, extract_upi_ids(clean))
    raws = PHONE_PATTERN.findall(clean)
    return _dedupe(_normalize_phone(r) for r in raws)


def extract_urls(text: str | None) -> list[str]:
    """Extract URLs, including bare shortener links (bit.ly/..., t.co/...).

    Scheme URLs are masked before the bare-domain pass so a link like
    `https://evil.com/login` is never also reported as `evil.com/login`.
    Matches are merged by position so the original order is preserved.
    """
    clean = _normalize_text(text)
    found: list[tuple[int, str]] = []
    scheme_spans = list(URL_SCHEME_PATTERN.finditer(clean))
    for match in scheme_spans:
        url = _clean_url(match.group())
        if url:
            found.append((match.start(), url))
    masked = _mask(clean, [match.group() for match in scheme_spans])
    for match in URL_BARE_PATTERN.finditer(masked):
        url = _clean_url(match.group())
        if url:
            found.append((match.start(), url))
    found.sort(key=lambda pair: pair[0])
    return _dedupe(url for _, url in found)


def extract_amounts(text: str | None) -> list[dict]:
    """Extract monetary amounts as [{'raw': 'Rs. 500', 'value': 500.0}, ...]."""
    clean = _normalize_text(text)
    clean = _mask(clean, extract_urls(clean))
    clean = _mask(clean, extract_upi_ids(clean))
    out: list[dict] = []
    for raw, multiplier in AMOUNT_PATTERN.findall(clean):
        entry = {"raw": raw, "value": _parse_amount(raw, multiplier)}
        if entry not in out:  # order-preserving dedupe
            out.append(entry)
    return out


# --------------------------------------------------------------------------- #
# Combined extraction — the function the pipeline calls
# --------------------------------------------------------------------------- #
def extract_entities(text: str | None) -> dict:
    """Extract all entity types from a message.

    Returns a JSON-serialisable dict:
        {
          "upi_ids":      ["fraud123@okaxis"],
          "phone_numbers": ["+919876543210"],   # always +91-normalised
          "urls":         ["bit.ly/claim-prize"],
          "amounts":      [{"raw": "Rs. 500", "value": 500.0}],
          "counts":       {"upi_ids": 1, ...},
          "total_entities": 3
        }
    Messy or empty input returns empty lists (never raises).
    """
    clean = _normalize_text(text)

    urls = extract_urls(clean)
    without_urls = _mask(clean, urls)

    upis = extract_upi_ids(without_urls)
    without_upi = _mask(without_urls, upis)

    phones = extract_phone_numbers(without_upi)
    amounts = extract_amounts(without_upi)

    entities = {
        "upi_ids": upis,
        "phone_numbers": phones,
        "urls": urls,
        "amounts": amounts,
    }
    entities["counts"] = {key: len(value) for key, value in entities.items()}
    entities["total_entities"] = sum(entities["counts"].values())
    return entities
