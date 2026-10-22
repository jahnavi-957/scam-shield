"""Shared fixtures for the backend test suite.

Integration tests run against the compose Postgres
(`docker compose up -d db`, exposed on 127.0.0.1:5433).
When it is not reachable, integration tests skip instead
of failing — the pure unit tests (alert rule, schemas)
never need a database.

The AI pipeline is ALWAYS mocked in tests: loading the
real DistilBERT + MiniLM models is far too slow for a
test suite (the real adapter is exercised by the ml
package's own tests).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

# Make `app` and the AI module (`scamshield_ml`) importable
# when pytest runs from the repo root.
for path in (str(BACKEND_DIR), str(REPO_DIR / "ml")):
    if path not in sys.path:
        sys.path.insert(0, path)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://scamshield:scamshield_dev@localhost:5433/scamshield",
)
# The app reads its DB URL from the environment; point it at
# the test database before any app import happens.
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("SSM_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "local")

from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402

EMBEDDING_DIM = 384


def _embedding(position: int) -> list[float]:
    """Deterministic 384-dim one-hot test vector."""
    vec = [0.0] * EMBEDDING_DIM
    vec[position] = 1.0
    return vec


def _fake_analyze(text: str) -> dict:
    """Deterministic stand-in for scamshield_ml.analyze_message.

    Scam verdicts embed as one-hot at position 0, legitimate
    ones at position 1 — orthogonal, so near-duplicate
    detection behaves predictably in tests."""
    lowered = text.lower()
    is_scam = any(
        keyword in lowered
        for keyword in ("congrats", "won", "prize", "kyc", "loan", "invest", "fraud")
    )
    return {
        "is_scam": is_scam,
        "scam_type": "fake_prize" if is_scam else "not_scam",
        "confidence": 0.9,
        "explanation": "stub verdict for tests",
        "embedding": _embedding(0 if is_scam else 1),
        "entities": {
            "upi_ids": ["fraud123@okaxis"] if "fraud123" in lowered else [],
            "phone_numbers": ["+919876543210"] if "9876543210" in lowered else [],
            "urls": ["bit.ly/claim-prize"] if "bit.ly" in lowered else [],
            "amounts": [],
            "counts": {},
            "total_entities": 0,
        },
    }


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip(
            "compose Postgres not reachable — run `docker compose up -d db` first"
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def clean_tables(db_engine):
    """Wipe all tables before each test (the repository
    functions commit, so rollback-based isolation is not
    an option)."""
    with db_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db_session(db_engine, clean_tables):
    db = sessionmaker(bind=db_engine, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_ai(monkeypatch):
    """Replace the AI pipeline with the deterministic stub."""
    monkeypatch.setattr("app.services.analysis.ai.analyze", _fake_analyze)
    return _fake_analyze


@pytest.fixture
def client(db_engine, clean_tables, mock_ai):
    """TestClient with the real startup lifespan (SSM is
    disabled via env, so bootstrap() uses env values)."""
    with TestClient(app) as test_client:
        yield test_client
