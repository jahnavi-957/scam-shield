"""Health endpoint: proves the API is up and can reach the database."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    """Return 200 when the API and DB are reachable, 503 otherwise.

    Orchestrators (Docker healthcheck, later ALB target group) use this to
    decide whether the instance can serve traffic.
    """
    try:
        db.execute(text("SELECT 1"))
        database = "connected"
    except Exception:
        database = "unavailable"

    healthy = database == "connected"
    if not healthy:
        response.status_code = 503

    return HealthResponse(
        status="ok" if healthy else "degraded",
        service="scamshield-backend",
        database=database,
    )