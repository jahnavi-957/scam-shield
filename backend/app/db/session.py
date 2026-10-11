"""Database engine, session factory and the FastAPI session dependency.

The engine is created ONCE at startup — after SSM secrets have been
loaded (see app.core.config.bootstrap) — rather than at import time.
Import-time creation would force a database URL to exist before the
app can even read its configuration, and it makes testing harder.

Connection pool sizing (single small EC2 instance, 1 gunicorn
worker): pool_size=5 steady + max_overflow=5 = at most 10
connections, which is deliberately small — a db.t3.micro RDS has
~100 max_connections and this app is its only client. pool_recycle
drops connections before RDS's idle timeout; pool_pre_ping heals
the occasional network blip of a private-subnet RDS.
"""

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def init_db(config: Any) -> None:
    """Create the engine and session factory from the runtime config.

    Idempotent: the first call wins (the engine is a singleton for
    the process lifetime)."""
    global _engine, SessionLocal
    if _engine is not None:
        return
    _engine = create_engine(
        config.database_url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def dispose_db() -> None:
    """Dispose the engine (shutdown / test teardown)."""
    global _engine, SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal = None


def get_db() -> Session:
    """FastAPI dependency: one session per request, closed afterwards.

    Defensive fallback: if the engine was not created at
    startup (e.g. a TestClient that never ran the lifespan),
    bootstrap it now — the app can always serve.
    """
    if SessionLocal is None:
        from app.core.config import bootstrap

        init_db(bootstrap())
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
