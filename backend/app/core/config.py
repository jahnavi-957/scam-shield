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
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Raised when the service cannot build a safe runtime configuration."""


class Settings(BaseSettings):
    """Non-secret settings; overridable via env vars / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scam Shield API"
    # local | dev | prod — also selects the SSM parameter path.
    environment: str = "local"

    # Required at runtime. Local Compose supplies it from the repository-root
    # `.env`; production supplies it from SSM. No connection string is baked
    # into the application defaults.
    database_url: str = ""

    # AWS
    aws_region: str = "us-east-1"
    ssm_enabled: bool = False
    ssm_prefix: str = "/scam-shield"

    # S3 / SNS (empty locally -> presigned URLs and alerts no-op)
    s3_bucket: str = ""
    sns_topic_arn: str = ""
    # Custom S3 endpoint: set to the internal MinIO URL for local dev.
    s3_endpoint_url: str = ""
    # Optional public URL used in presigned responses when the API can reach
    # MinIO by an internal hostname but the browser must use localhost.
    s3_public_endpoint_url: str = ""
    s3_force_path_style: bool = True
    # Optional explicit credentials for local MinIO. AWS deployments should
    # use the instance/task role instead.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    sns_mock_enabled: bool = False

    # Alert rule: fire when an entity reaches N reports within M minutes.
    alert_threshold: int = 5
    alert_window_minutes: int = 1440  # 24 hours

    # Presigned upload URL lifetime (seconds).
    # 5 minutes: short-lived capability — just long enough for the
    # frontend to upload, tight enough to limit abuse.
    presign_expiry_seconds: int = Field(default=300, ge=1, le=300)

    # OCR engine: tesseract (local binary) | textract (AWS service)
    ocr_engine: str = "tesseract"

    # Model weights: pulled from S3 at container startup when a
    # bucket is configured; never baked into the Docker image.
    model_s3_bucket: str = ""
    model_s3_key: str = "scam-shield/model/"
    model_dir: str = "/var/lib/scamshield/model"

    # Input limits
    max_text_length: int = Field(default=10_000, ge=1, le=100_000)
    max_payload_bytes: int = Field(default=2 * 1024 * 1024, ge=1, le=20 * 1024 * 1024)
    max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=20 * 1024 * 1024)
    max_image_width: int = Field(default=4096, ge=1, le=16_384)
    max_image_height: int = Field(default=4096, ge=1, le=16_384)
    max_image_pixels: int = Field(default=16_777_216, ge=1, le=268_435_456)

    # In-memory abuse controls. The limiter intentionally does not persist or
    # log the requester address.
    analysis_rate_limit_per_minute: int = Field(default=20, ge=1, le=10_000)
    analysis_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)

    # Security headers. HSTS is opt-in so local HTTP development is not
    # pinned to HTTPS; production deployments should enable it at the edge or
    # set this flag when TLS terminates in the application.
    security_headers_enabled: bool = True
    hsts_enabled: bool = False

    # Frontend origins allowed by CORS
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )
    cors_methods: str = "GET,POST,PUT,DELETE,OPTIONS,HEAD"
    cors_headers: str = (
        "Accept,Content-Type,Origin,X-Requested-With,Cache-Control,Pragma,Authorization"
    )

    @property
    def cors_origins_as_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cors_methods_as_list(self) -> list[str]:
        return [method.strip().upper() for method in self.cors_methods.split(",") if method.strip()]

    @property
    def cors_headers_as_list(self) -> list[str]:
        return [header.strip() for header in self.cors_headers.split(",") if header.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if "*" in self.cors_methods_as_list or "*" in self.cors_headers_as_list:
            raise ValueError("wildcard CORS methods and headers are not permitted")
        if "*" in self.cors_origins_as_list:
            raise ValueError("wildcard CORS origins are not permitted")
        if self.environment.lower() == "prod" and self.ssm_enabled:
            if not self.ssm_prefix.strip():
                raise ValueError("SSM_PREFIX is required when production SSM is enabled")
        if self.environment.lower() == "prod" and any(
            not origin.lower().startswith("https://") for origin in self.cors_origins_as_list
        ):
            raise ValueError("production CORS origins must use HTTPS")
        if self.environment.lower() == "prod":
            for endpoint in (self.s3_endpoint_url, self.s3_public_endpoint_url):
                if endpoint and not endpoint.lower().startswith("https://"):
                    raise ValueError("production S3 endpoints must use HTTPS")
            if any((self.aws_access_key_id, self.aws_secret_access_key, self.aws_session_token)):
                raise ValueError("production AWS credentials must come from the instance role")
        return self

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
    full_names = [f"{settings.ssm_path}/{name}" for name in SSM_SECRET_NAMES]

    try:
        ssm = boto3.client("ssm", region_name=settings.aws_region)
        response = ssm.get_parameters(Names=full_names, WithDecryption=True)
    except Exception as exc:
        if settings.environment.lower() == "prod":
            logger.critical("SSM get_parameters failed in production; refusing fallback")
            raise ConfigurationError("Production secrets could not be loaded from SSM") from exc
        logger.error("SSM get_parameters failed; falling back to env values", exc_info=True)
        return {}

    found = {
        param["Name"].rsplit("/", 1)[-1]: param["Value"]
        for param in response.get("Parameters", [])
    }
    missing = [name for name in full_names if name.rsplit("/", 1)[-1] not in found]
    if missing:
        if settings.environment.lower() == "prod":
            logger.critical("Required SSM parameters are missing in production")
            raise ConfigurationError("Required production secrets are missing from SSM")
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
    runtime = RuntimeConfig(settings, secrets)
    if not runtime.database_url:
        raise ConfigurationError("DATABASE_URL is required")
    if settings.environment.lower() == "prod" and (
        not runtime.s3_bucket or not runtime.sns_topic_arn
    ):
        raise ConfigurationError(
            "Production S3_BUCKET and SNS_TOPIC_ARN are required from SSM"
        )
    return runtime
