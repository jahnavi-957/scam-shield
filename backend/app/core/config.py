"""Core configuration. Settings come from environment variables (or backend/.env in local dev)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, overridable via environment variables.

    Everything here is non-secret configuration. Secrets will be injected
    from AWS SSM Parameter Store once we deploy (M4), never from this file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Scam Shield API"
    environment: str = "local"

    # Default points at the compose database (service name `db`).
    database_url: str = "postgresql+psycopg://scamshield:scamshield_dev@db:5432/scamshield"

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_as_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()