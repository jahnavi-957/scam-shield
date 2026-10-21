"""Model weights loader: pull the fine-tuned DistilBERT from S3 at
container startup.

Why weights come from S3 and are NOT baked into the Docker image
(viva talking point): retraining only re-uploads to S3, and every
container picks up the new model on its next start — no image
rebuild, no registry push, no redeploy of anything else. The
download is one-time per instance; afterwards the model is read
from the local disk path exposed to the ml package via
``SCAM_MODEL_DIR``.

Failures degrade gracefully: if the download fails (no bucket
configured, no network yet), the ml package falls back to its
transparent rule-based classifier, so the API still serves.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def download_model_if_needed(config) -> bool:
    """Ensure a local copy of the fine-tuned model exists.

    Returns True when a usable model directory is present
    (already on disk, or freshly downloaded from S3).
    """
    if not config.model_s3_bucket:
        logger.info(
            "no model S3 bucket configured; "
            "using rule-based fallback unless a local model exists"
        )
        return _model_present(config.model_dir)

    model_dir = Path(config.model_dir)
    if _model_present(model_dir):
        logger.info("model weights already present at %s", model_dir)
        os.environ["SCAM_MODEL_DIR"] = str(model_dir)
        return True

    try:
        model_dir.mkdir(parents=True, exist_ok=True)
        from app.services.storage import create_s3_client

        s3 = create_s3_client(config)
        paginator = s3.get_paginator("list_objects_v2")
        downloaded = 0
        for page in paginator.paginate(Bucket=config.model_s3_bucket, Prefix=config.model_s3_key):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):  # directory marker
                    continue
                relative = key[len(config.model_s3_key):].lstrip("/")
                if not relative:
                    continue
                target = (model_dir / relative).resolve()
                if model_dir.resolve() not in target.parents:
                    raise ValueError("model object path escapes the configured model directory")
                target.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(config.model_s3_bucket, key, str(target))
                downloaded += 1
        if downloaded == 0:
            logger.warning("no model files found under s3://%s/%s", config.model_s3_bucket, config.model_s3_key)
            return False
        os.environ["SCAM_MODEL_DIR"] = str(model_dir)
        logger.info("downloaded %d model files from S3 to %s", downloaded, model_dir)
        return True
    except Exception:
        logger.error(
            "model download from S3 failed; "
            "continuing with rule-based fallback classifier",
            exc_info=True,
        )
        return False


def _model_present(model_dir: str | Path) -> bool:
    return (Path(model_dir) / "config.json").is_file()
