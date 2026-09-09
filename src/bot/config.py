import re
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False, hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"] = "development"
    bot_token: SecretStr = SecretStr("")
    webhook_secret: SecretStr = SecretStr("development-only-change-before-deploy")
    webhook_url: str = ""
    webhook_path: str = "/telegram/webhook"
    database_url: SecretStr = SecretStr("postgresql+asyncpg://bot:bot@localhost:5432/bot")
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    host: str = "0.0.0.0"  # noqa: S104 - container listener; host publish is loopback-only
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    metrics_token: SecretStr = SecretStr("")
    sentry_dsn: SecretStr = SecretStr("")
    release: str = "development"
    admin_ids: list[int] = Field(default_factory=list)
    user_rate_limit: int = Field(default=10, ge=1, le=10000)
    user_rate_window: int = Field(default=10, ge=1, le=3600)
    ingress_rate_limit: int = Field(default=2000, ge=1)
    ingress_rate_window: int = Field(default=1, ge=1, le=60)
    max_body_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    worker_poll_seconds: float = Field(default=0.5, ge=0.05, le=30)
    worker_timeout_seconds: int = Field(default=30, ge=1, le=120)
    worker_max_attempts: int = Field(default=5, ge=1, le=20)
    inbox_retention_days: int = Field(default=7, ge=1, le=365)

    @field_validator("webhook_path")
    @classmethod
    def valid_path(cls, value: str) -> str:
        if not re.fullmatch(r"/[A-Za-z0-9/_-]+", value) or value.startswith("//"):
            raise ValueError("WEBHOOK_PATH must be an absolute URL path without query parameters")
        if value.rstrip("/") in {"/health/live", "/health/ready", "/metrics"}:
            raise ValueError("WEBHOOK_PATH conflicts with a reserved endpoint")
        return value

    @field_validator("webhook_secret")
    @classmethod
    def valid_secret(cls, value: SecretStr) -> SecretStr:
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", value.get_secret_value()):
            raise ValueError("WEBHOOK_SECRET must contain 32–256 letters, digits, '_' or '-'")
        return value

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        redis_url = self.redis_url.get_secret_value()
        if not redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        if self.webhook_url:
            url = urlsplit(self.webhook_url)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or url.path != self.webhook_path
            ):
                raise ValueError("WEBHOOK_URL must be HTTPS and its path must equal WEBHOOK_PATH")
        if self.environment == "production":
            if not self.webhook_url:
                raise ValueError("Production requires WEBHOOK_URL")
            if self.webhook_secret.get_secret_value().startswith("development-"):
                raise ValueError("Production requires a generated WEBHOOK_SECRET")
            if len(self.metrics_token.get_secret_value()) < 32:
                raise ValueError("Production requires a METRICS_TOKEN of at least 32 characters")
            if urlsplit(database_url).password in {None, "", "bot", "postgres", "password"}:
                raise ValueError("Production requires a non-default database password")
            if not urlsplit(redis_url).password:
                raise ValueError("Production requires Redis authentication")
        return self

    def require_bot_token(self) -> str:
        token = self.bot_token.get_secret_value()
        if not token:
            raise ValueError("BOT_TOKEN is required for worker and Telegram management commands")
        return token
