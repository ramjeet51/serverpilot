"""Centralised, validated configuration for the backend, worker and agent gateway.

Values are loaded (lowest to highest precedence) from:
  1. <project root>/.env       shared platform settings
  2. backend/.env              backend-only secrets and settings
  3. process environment       (PM2 / shell exports)
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

_PLACEHOLDER_MARKERS = ("change-me", "changeme", "replace-me", "placeholder")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "ServerPilot"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_debug: bool = False
    app_secret_key: SecretStr
    app_timezone: str = "UTC"
    api_docs_enabled: bool = True

    # Backend
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    backend_workers: int = Field(default=1, ge=1, le=32)
    cors_origins: str = "http://localhost:3000"

    # Database
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "serverpilot"
    postgres_user: str = "serverpilot"
    postgres_password: SecretStr = SecretStr("")
    database_url: str | None = None
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)

    # Redis / Celery
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: SecretStr = SecretStr("")
    redis_db: int = 0
    redis_url: str | None = None
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_concurrency: int = Field(default=2, ge=1)

    # Agent gateway
    agent_gateway_host: str = "127.0.0.1"
    agent_gateway_port: int = Field(default=8001, ge=1, le=65535)
    agent_heartbeat_interval: int = Field(default=15, ge=1)
    agent_offline_timeout: int = Field(default=60, ge=5)
    agent_auth_mode: Literal["mtls", "test_token"] = "mtls"
    agent_certificate_path: str = "certs/agents"
    # URL the agent should dial. Empty builds ws://AGENT_GATEWAY_HOST:AGENT_GATEWAY_PORT/v1/connect.
    # Set this when agents reach the gateway through a tunnel (often ws://127.0.0.1:8001/v1/connect).
    agent_advertised_url: str = ""
    agent_registration_ttl_hours: int = Field(default=24, ge=1, le=168)

    # Security
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, ge=1)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1)
    require_mfa: bool = False
    cookie_secure: bool = False
    login_rate_limit_attempts: int = Field(default=5, ge=1)
    login_rate_limit_window_seconds: int = Field(default=300, ge=10)
    account_lockout_threshold: int = Field(default=10, ge=1)
    account_lockout_minutes: int = Field(default=15, ge=1)
    api_rate_limit_per_minute: int = Field(default=300, ge=1)
    initial_admin_email: str | None = None
    initial_admin_password: SecretStr | None = None

    # Jobs
    job_default_timeout_seconds: int = Field(default=600, ge=5)
    job_max_timeout_seconds: int = Field(default=3600, ge=5)

    # File management
    max_upload_size_mb: int = Field(default=100, ge=1)
    file_operation_timeout: int = Field(default=30, ge=1)
    allowed_file_roots: str = "/home,/var/www,/etc/nginx,/opt"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    log_directory: str = "logs"

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        if self.require_mfa:
            raise ValueError("REQUIRE_MFA=true is not supported until Phase 7 (TOTP enrolment).")
        for name in ("app_secret_key", "jwt_secret_key"):
            value = getattr(self, name).get_secret_value()
            if self.app_env == "production":
                if len(value) < 32 or any(m in value.lower() for m in _PLACEHOLDER_MARKERS):
                    raise ValueError(f"{name.upper()} must be a random value of at least 32 characters in production.")
        if self.app_env == "production" and self.app_debug:
            raise ValueError("APP_DEBUG must be false in production.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_file_root_list(self) -> list[str]:
        return [p.strip() for p in self.allowed_file_roots.split(",") if p.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password.get_secret_value(), safe="")
        auth = f"{user}:{password}" if password else user
        return f"postgresql+psycopg://{auth}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        password = self.redis_password.get_secret_value()
        auth = f":{quote(password, safe='')}@" if password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_dsn

    @property
    def celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_dsn

    @property
    def log_path(self) -> Path:
        path = Path(self.log_directory)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def gateway_base_url(self) -> str:
        return f"http://{self.agent_gateway_host}:{self.agent_gateway_port}"

    @property
    def agent_ws_url(self) -> str:
        if self.agent_advertised_url.strip():
            return self.agent_advertised_url.strip().rstrip("/")
        return f"ws://{self.agent_gateway_host}:{self.agent_gateway_port}/v1/connect"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
