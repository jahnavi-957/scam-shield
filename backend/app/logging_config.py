"""Structured JSON logging for CloudWatch.

Every log line is a JSON object — CloudWatch Logs Insights
can then query fields directly (e.g.
`filter is_scam = true | stats count() by scam_type`).
"""

from __future__ import annotations

import logging

from pythonjsonlogger import jsonlogger

# Noisy libraries: keep their output at WARNING so request
# logs stay readable in CloudWatch.
QUIET_LOGGERS = (
    "urllib3",
    "botocore",
    "boto3",
    "sentence_transformers",
    "transformers",
    "torch",
)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with a JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
