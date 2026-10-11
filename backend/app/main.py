"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Scam Shield API",
    description="Backend for the Scam Shield scam-intelligence platform.",
    version="0.1.0",
)

# In production the browser talks to the same origin (ALB), so CORS stays
# narrow; for local dev the Vite dev server on :5173 needs it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_as_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}