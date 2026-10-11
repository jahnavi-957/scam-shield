# ---------- builder: dependencies into a virtualenv ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# CPU-only PyTorch first: the default PyPI linux wheel bundles
# CUDA (~2 GB); the CPU wheel is ~200 MB — right-sized for a
# small EC2 instance. The second install sees torch as already
# satisfied and skips it.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2,<3"

COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install ./backend

# ---------- runtime ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/opt/ml"

# tesseract-ocr: the default OCR engine (apt package).
# Unprivileged user: the container never runs as root.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser \
    && mkdir -p /var/lib/scamshield \
    && chown appuser /var/lib/scamshield

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# The API + migrations + start script.
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts

# The AI module (scamshield_ml) rides on PYTHONPATH — the
# backend imports analyze_message() from it.
COPY ml/scamshield_ml /opt/ml/scamshield_ml

RUN chmod +x scripts/start.sh

USER appuser
EXPOSE 8000

CMD ["sh", "./scripts/start.sh"]
