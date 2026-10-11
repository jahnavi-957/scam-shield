"""SNS alerting + the report-threshold rule.

The rule (and why it works this way — viva talking point):

``should_alert`` fires when the number of reports mentioning an
entity within the trailing window reaches ``threshold`` (default
5 reports / 24 hours). It fires on EXACTLY the Nth report — the
check is ``count >= threshold``, evaluated after the current
report is linked, so with threshold=5 the 5th report in 24h
triggers the alert, not the 4th and not the 6th.

``last_alert_at`` is a cooldown: while it falls inside the
current window, further reports do NOT re-alert (a burst of 20
reports produces one alert, not sixteen). The alert re-arms once
the window slides past ``last_alert_at`` — and only if the count
is still at or above the threshold at that point.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import boto3

logger = logging.getLogger(__name__)

_sns = None
_topic_arn: str = ""
_window = timedelta(hours=24)


def init_alerts(config) -> None:
    """Bind the SNS client, topic ARN and alert window at startup."""
    global _sns, _topic_arn, _window
    _sns = boto3.client("sns", region_name=config.aws_region)
    _topic_arn = config.sns_topic_arn
    _window = timedelta(minutes=config.alert_window_minutes)


def should_alert(
    report_count_in_window: int,
    *,
    threshold: int,
    last_alert_at: datetime | None,
    now: datetime,
    window: timedelta,
) -> bool:
    """Pure decision function — no AWS calls, fully unit-testable.

    True only when (a) the windowed report count has reached the
    threshold, and (b) no alert was published within the current
    window (cooldown). See the module docstring for the rationale.
    """
    if report_count_in_window < threshold:
        return False
    if last_alert_at is not None and now - last_alert_at < window:
        return False
    return True


def publish_alert(entity_value: str, entity_type: str, report_count: int) -> bool:
    """Publish an alert to the configured SNS topic.

    Returns True when a message was published. With no topic
    configured (local dev) it logs and returns False — alerts are
    never the critical path of a classification request.
    """
    if not _topic_arn:
        logger.debug(
            "no SNS topic configured; skipping alert for %s (%d reports)",
            entity_value,
            report_count,
        )
        return False
    message = (
        f"Scam Shield alert: entity '{entity_value}' (type: {entity_type}) "
        f"has been reported {report_count} times in the last "
        f"{int(_window.total_seconds() // 60)} minutes. "
        "Investigate this entity and consider blocking it."
    )
    _sns.publish(
        TopicArn=_topic_arn,
        Subject=f"Scam Shield: {report_count} reports for {entity_value}",
        Message=message,
    )
    logger.info(
        "sns alert published",
        extra={"entity_value": entity_value, "entity_type": entity_type, "report_count": report_count},
    )
    return True
