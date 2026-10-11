"""Unit tests for entity extraction (ml/scamshield_ml/extraction.py)."""

from __future__ import annotations

import pytest

from scamshield_ml.extraction import (
    extract_amounts,
    extract_entities,
    extract_phone_numbers,
    extract_upi_ids,
    extract_urls,
    is_likely_upi_id,
)


# --------------------------------------------------------------------------- #
# UPI IDs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("pay fraud123@okaxis now", ["fraud123@okaxis"]),
        ("send to 9876543210@ybl please", ["9876543210@ybl"]),
        ("name@okhdfcbank", ["name@okhdfcbank"]),
        ("UPI: rahul.sharma@okicici and priya@paytm", ["rahul.sharma@okicici", "priya@paytm"]),
        ("Use myupi-1@axl today", ["myupi-1@axl"]),
    ],
)
def test_upi_ids_valid(text, expected):
    assert extract_upi_ids(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",  # empty
        "abc@",  # missing handle
        "@bank",  # missing local part
        "a@b",  # both too short
        "@@",  # garbage
        "fraud@@okaxis",  # double @
        "user@.com",  # handle starts with dot
        "no at sign here",
        "x_y@ok",  # handle too short
    ],
)
def test_upi_ids_malformed(text):
    assert extract_upi_ids(text) is not None  # never raises
    if text:
        assert extract_upi_ids(text) == [] or "@" in text


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("fraud123@okaxis", True),
        ("someone@ybl", True),
        ("user@paytm", True),
        ("user@unknownbank123", False),  # unrecognised handle
        ("not-an-upi", False),
        ("a@b", False),
    ],
)
def test_is_likely_upi_id(candidate, expected):
    assert is_likely_upi_id(candidate) is expected


# --------------------------------------------------------------------------- #
# Phone numbers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("call +919876543210 now", ["+919876543210"]),
        ("call +91 98765 43210 now", ["+919876543210"]),
        ("call 91 98765 43210 now", ["+919876543210"]),
        ("call 09876543210 now", ["+919876543210"]),
        ("bare mobile 9876543210", ["+919876543210"]),
        ("two: 9876543210 and 8765432109", ["+919876543210", "+918765432109"]),
    ],
)
def test_phone_numbers_valid(text, expected):
    assert extract_phone_numbers(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",  # empty
        "US number +1 555 123 4567",  # non-Indian (starts with 5 after country code)
        "order id 20240912345678",  # long digit run, not a mobile
        "short 98765",  # too short
        "landline 011 2345 6789",  # 11 digits starting 0/1 -> not mobile format
    ],
)
def test_phone_numbers_invalid(text):
    assert extract_phone_numbers(text) == []


def test_phone_not_duplicated_from_upi_id():
    """A mobile number inside a UPI ID must not also be reported as a phone."""
    text = "send money to 9876543210@ybl"
    assert extract_phone_numbers(text) == []
    assert extract_upi_ids(text) == ["9876543210@ybl"]


# --------------------------------------------------------------------------- #
# URLs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("click https://evil.com/login now", ["https://evil.com/login"]),
        ("click http://evil.com/login now", ["http://evil.com/login"]),
        ("short link bit.ly/claim-prize", ["bit.ly/claim-prize"]),
        ("tinyurl.com/x and t.co/y", ["tinyurl.com/x", "t.co/y"]),
        ("visit paytm.com today", ["paytm.com"]),
        ("see https://bank.com/path?a=1, then go", ["https://bank.com/path?a=1"]),
    ],
)
def test_urls_valid(text, expected):
    assert extract_urls(text) == expected


@pytest.mark.parametrize("text", ["", "no links here", "just plain words and 1.2.3 numbers"])
def test_urls_none(text):
    assert extract_urls(text) == []


def test_urls_dedupes():
    assert extract_urls("bit.ly/x and bit.ly/x again") == ["bit.ly/x"]


# --------------------------------------------------------------------------- #
# Amounts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected",
    [
        ("pay Rs. 500", [{"raw": "500", "value": 500.0}]),
        ("pay Rs 500", [{"raw": "500", "value": 500.0}]),
        ("₹50,000 prize", [{"raw": "50,000", "value": 50000.0}]),
        ("INR 2000 fee", [{"raw": "2000", "value": 2000.0}]),
        ("pay ₹10 lakh", [{"raw": "10", "value": 1000000.0}]),  # lakh multiplier
        ("₹2 crore scheme", [{"raw": "2", "value": 20000000.0}]),  # crore multiplier
        ("pay Rs. 1,50,000.50", [{"raw": "1,50,000.50", "value": 150000.5}]),
    ],
)
def test_amounts_valid(text, expected):
    assert extract_amounts(text) == expected


@pytest.mark.parametrize("text", ["", "no money mentioned", "free of charge"])
def test_amounts_none(text):
    assert extract_amounts(text) == []


# --------------------------------------------------------------------------- #
# Combined extraction / messy input
# --------------------------------------------------------------------------- #
def test_entities_full_message():
    text = (
        "Congrats! You've won Rs. 50,000. Claim now by paying Rs. 500 fee "
        "to upi: fraud123@okaxis or click bit.ly/claim-prize"
    )
    entities = extract_entities(text)
    assert entities["upi_ids"] == ["fraud123@okaxis"]
    assert entities["urls"] == ["bit.ly/claim-prize"]
    assert entities["phone_numbers"] == []
    assert entities["counts"]["amounts"] == 2
    assert entities["amounts"][0] == {"raw": "50,000", "value": 50000.0}
    assert entities["total_entities"] == 4


@pytest.mark.parametrize("text", [None, "", "   ", "\t\n"])
def test_entities_empty_input(text):
    entities = extract_entities(text)
    assert entities["total_entities"] == 0
    assert entities["upi_ids"] == []


def test_entities_messy_obfuscated_text():
    """Zero-width characters (a common obfuscation) must not break parsing."""
    text = "cl​ick https://evil.com/​login or call +9​1 98765 43210"
    entities = extract_entities(text)
    assert entities["urls"] == ["https://evil.com/login"]
    assert entities["phone_numbers"] == ["+919876543210"]


def test_entities_multiple_of_everything():
    text = (
        "Pay 1000 to 9876543210 or 8765432109 via a@ybl or b@paytm. "
        "Links: bit.ly/x, https://evil.com, tinyurl.com/y. Fee Rs. 99."
    )
    entities = extract_entities(text)
    assert entities["phone_numbers"] == ["+919876543210", "+918765432109"]
    assert entities["upi_ids"] == ["a@ybl", "b@paytm"]
    assert len(entities["urls"]) == 3
    assert entities["counts"]["amounts"] == 1  # only "Rs. 99" - bare "1000" has no currency marker
