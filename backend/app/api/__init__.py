"""API routing package."""

from fastapi import APIRouter

from app.api import analyze, entities, health, uploads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(analyze.router)
api_router.include_router(uploads.router)
api_router.include_router(entities.router)
