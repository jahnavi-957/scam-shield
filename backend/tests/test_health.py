"""Health endpoint tests.

Unit tests use a fake DB session (no Postgres required).
The integration test runs against the compose Postgres.
"""

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

client = TestClient(app)


class _UnavailableDB:
    """Fake session that behaves like a database that cannot be reached."""

    def execute(self, *args, **kwargs):
        raise RuntimeError("database unreachable")


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Scam Shield API"


def test_health_reports_degraded_when_database_down():
    def override_get_db():
        yield _UnavailableDB()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"] == "unavailable"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_health_connected_against_real_database(db_engine):
    """Requires the compose Postgres to be up (docker compose up -d db)."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "connected"
    assert body["status"] == "ok"