FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy packaging metadata first for efficient layer caching.
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY tests ./tests

RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir ".[dev]"

RUN chmod +x scripts/start.sh

EXPOSE 8000

CMD ["sh", "./scripts/start.sh"]