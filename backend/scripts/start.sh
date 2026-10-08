#!/bin/sh
# Container start script: apply migrations, then serve the API.
set -e

echo "[start.sh] Applying database migrations..."
alembic upgrade head

echo "[start.sh] Starting API server on :${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"