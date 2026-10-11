"""Configuration: typed settings (pydantic-settings) + SSM secrets.

Two layers, by design:

* ``Settings`` — non-secret configuration from environment
  variables (or ``backend/.env`` in local dev). Safe to print.
* ``RuntimeConfig`` — the effective config at runtime: settings
  with SSM Parameter Store secrets overlaid on top. Produced once
  at container startup by ``bootstrap()``.

Why SSM in production (and not .env): secrets never touch the
repository, the Docker image or the EC2 filesystem; the EC2
instance role can be granted ``ssm:GetParameters`` on just the
/scam-shield path (least privilege); rotation and CloudTrail
auditing come for free. Locally the same code reads plain env
vars, so nothing about the app logic changes between dev and AWS.

Note: the AWS *region* itself cannot come from SSM — you need a
region to build the SSM client in the first place (bootstrapping
problem). Region therefore comes from env / the EC2 instance
metadata, like every other boto3 client on the instance.
"""

from functools import lru_cache
from typing import Any

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Non-secret settings; overridable via env vars / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scam Shield API"
    # local | dev | prod — also selects the SSM parameter path.
    environment: str = "local"

    # Database (compose default points at the service name `db`).
    database_url: str = "postgresql+psycopg://scamshield:scamshield_dev@db:5432/scamshield"

    # AWS
    aws_region: str = "us-east-1"
    ssm_enabled: bool = False
    ssm_prefix: str = "/scam-shield"

    # S3 / SNS (empty locally -> presigned URLs and alerts no-op)
    s3_bucket: str = ""
    sns_topic_arn: str = ""

    # Alert rule: fire when an entity reaches N reports within M minutes.
    alert_threshold: int = 5
    alert_window_minutes: int = 1440  # 24 hours

    # Presigned upload URL lifetime (seconds).
    presign_expiry_seconds: int = 900

    # OCR engine: tesseract (local binary) | textract (AWS service)
    ocr_engine: str = "tesseract"

    # Model weights: pulled from S3 at container startup when a
    # bucket is configured; never baked into the Docker image.
    model_s3_bucket: str = ""
    model_s3_key: str = "scam-shield/model/"
    model_dir: str = "/var/lib/scamshield/model"

    # Input limits
    max_text_length: int = 10_000
    max_payload_bytes: int = 2 * 1024 * 1024  # 2 MB

    # Frontend origins allowed by CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_as_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ssm_path(self) -> str:
        return f"{self.ssm_prefix}/{self.environment}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Names of the secure parameters stored in SSM, keyed by their
# leaf name (the full path is <ssm_prefix>/<environment>/<name>).
SSM_SECRET_NAMES = ("database_url", "s3_bucket", "sns_topic_arn")


def load_secrets_from_ssm(settings: Settings) -> dict[str, str]:
    """Fetch secure parameters from AWS SSM Parameter Store.

    Returns a dict of {leaf_name: value}; missing parameters are
    logged and skipped (the env/default value then applies). In
    local dev (ssm_enabled=False) this returns {} immediately.

    Values returned here are secrets — never log them.
    """
    if not settings.ssm_enabled:
        return {}

    import logging

    logger = logging.getLogger(__name__)
    ssm = boto3.client("ssm", region_name=settings.aws_region)
    full_names = [f"{settings.ssm_path}/{name}" for name in SSM_SECRET_NAMES]

    try:
        response = ssm.get_parameters(Names=full_names, WithDecryption=True)
    except Exception:
        logger.error("SSM get_parameters failed; falling back to env values", exc_info=True)
        return {}

    found = {
        param["Name"].rsplit("/", 1)[-1]: param["Value"]
        for param in response.get("Parameters", [])
    }
    missing = [name for name in full_names if name.rsplit("/", 1)[-1] not in found]
    if missing:
        logger.warning("SSM parameters not found (env values will apply): %s", missing)
    return found


class RuntimeConfig:
    """Effective configuration: Settings with SSM secrets overlaid.

    Attribute access delegates to Settings; the three secret-backed
    attributes prefer the SSM value. ``__repr__`` is redacted so a
    stray ``logger.info(config)`` can never leak a database URL.
    """

    def __init__(self, settings: Settings, secrets: dict[str, str]):
        self._settings = settings
        self._secrets = secrets

    def __getattr__(self, name: str) -> Any:
        return getattr(self._settings, name)

    @property
    def database_url(self) -> str:
        return self._secrets.get("database_url") or self._settings.database_url

    @property
    def s3_bucket(self) -> str:
        return self._secrets.get("s3_bucket") or self._settings.s3_bucket

    @property
    def sns_topic_arn(self) -> str:
        return self._secrets.get("sns_topic_arn") or self._settings.sns_topic_arn

    def __repr__(self) -> str:
        return (
            f"RuntimeConfig(environment={self._settings.environment!r}, "
            f"ssm_enabled={self._settings.ssm_enabled!r}, secrets=<redacted>)"
        )


def bootstrap() -> RuntimeConfig:
    """Build the effective config: env settings overlaid with SSM
    secrets. Called once at container startup (FastAPI lifespan)."""
    settings = get_settings()
    secrets = load_secrets_from_ssm(settings)
    return RuntimeConfig(settings, secrets)
