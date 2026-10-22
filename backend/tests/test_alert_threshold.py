"""Unit tests for the SNS alert-threshold rule.

Pure logic, no database, no AWS — these run anywhere.
The rule must fire EXACTLY at the configured report
count, not one report early and not one late.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.alerts import should_alert

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
WINDOW = timedelta(hours=24)


def test_no_alert_below_threshold():
    assert should_alert(4, threshold=5, last_alert_at=None, now=NOW, window=WINDOW) is False


def test_alert_fires_exactly_at_threshold():
    """The 5th report in the window is the one that alerts."""
    assert should_alert(5, threshold=5, last_alert_at=None, now=NOW, window=WINDOW) is True


def test_alert_fires_above_threshold_when_never_alerted():
    assert should_alert(7, threshold=5, last_alert_at=None, now=NOW, window=WINDOW) is True


def test_no_duplicate_alert_inside_cooldown_window():
    """Already alerted 1 hour ago -> no second alert,
    even though the count is still above the threshold."""
    assert (
        should_alert(
            6,
            threshold=5,
            last_alert_at=NOW - timedelta(hours=1),
            now=NOW,
            window=WINDOW,
        )
        is False
    )


def test_alert_rearms_after_window_slides_past_last_alert():
    """Last alert was 25 hours ago (> 24h window) -> the
    rule is armed again, provided the count still qualifies."""
    assert (
        should_alert(
            6,
            threshold=5,
            last_alert_at=NOW - WINDOW - timedelta(minutes=1),
            now=NOW,
            window=WINDOW,
        )
        is True
    )


def test_no_rearm_when_count_dropped_below_threshold():
    """Window slid past the last alert, but only 3 reports
    remain in the window -> still no alert."""
    assert (
        should_alert(
            3,
            threshold=5,
            last_alert_at=NOW - WINDOW - timedelta(minutes=1),
            now=NOW,
            window=WINDOW,
        )
        is False
    )


def test_custom_threshold():
    assert should_alert(2, threshold=3, last_alert_at=None, now=NOW, window=WINDOW) is False
    assert should_alert(3, threshold=3, last_alert_at=None, now=NOW, window=WINDOW) is True


def test_boundary_is_inclusive_not_off_by_one():
    """count == threshold alerts; count == threshold - 1 does not."""
    assert should_alert(4, threshold=5, last_alert_at=None, now=NOW, window=WINDOW) is False
    assert should_alert(5, threshold=5, last_alert_at=None, now=NOW, window=WINDOW) is True
