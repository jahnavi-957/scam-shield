#!/bin/sh
# Container start script: apply migrations, pull the model
# weights from S3, then serve the API.
set -e

echo "[start.sh] Applying database migrations..."
alembic upgrade head

echo "[start.sh] Checking for model weights in S3..."
# One-time download per instance; on failure the app falls
# back to the rule-based classifier (see model_loader.py).
python -c "from app.core.config import bootstrap; from app.services.model_loader import download_model_if_needed; download_model_if_needed(bootstrap())"

echo "[start.sh] Starting API server on :${PORT:-8000}"
# 1 worker: each worker loads the ML model into memory,
# so a single worker is the right sizing for a small EC2
# instance (gunicorn gives us crash-restart supervision).
exec gunicorn -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:${PORT:-8000} app.main:app
