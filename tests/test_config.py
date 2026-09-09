import pytest
from pydantic import ValidationError

from bot.config import Settings


def test_safe_development_defaults(settings):
    assert settings.bot_token.get_secret_value() == ""
    assert settings.worker_timeout_seconds == 30
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        settings.require_bot_token()


@pytest.mark.parametrize(
    "path", ["webhook", "//host", "/webhook?token=a", "/metrics", "/health/live/"]
)
def test_reject_invalid_webhook_paths(path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, webhook_path=path)


@pytest.mark.parametrize("secret", ["", "short", "a" * 257, "x!" * 30])
def test_reject_invalid_secrets(secret):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, webhook_secret=secret)


@pytest.mark.parametrize(
    "url",
    [
        "http://bot.example.com/telegram/webhook",
        "https://user:password@bot.example.com/telegram/webhook",
        "https://bot.example.com/wrong",
        "https://bot.example.com/telegram/webhook?key=value",
    ],
)
def test_reject_invalid_public_webhook_urls(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, webhook_url=url)


def test_production_rejects_default_config():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")


def test_production_accepts_explicit_secure_settings():
    settings = Settings(
        _env_file=None,
        environment="production",
        webhook_url="https://bot.example.com/telegram/webhook",
        webhook_secret="s" * 48,
        metrics_token="m" * 48,
        database_url="postgresql+asyncpg://bot:a-long-generated-secret@postgres/bot",
        redis_url="redis://:a-long-generated-secret@redis/0",
    )
    assert "a-long-generated-secret" not in repr(settings)


@pytest.mark.parametrize(
    "override",
    [
        {"database_url": "sqlite:///tmp/bot.db"},
        {"redis_url": "http://redis:6379"},
        {"user_rate_limit": 0},
        {"worker_timeout_seconds": 0},
    ],
)
def test_invalid_dependency_and_limit_settings(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **override)


def test_validation_errors_do_not_print_secret_values():
    private = "THIS_IS_A_SECRET!"
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, webhook_secret=private)
    assert private not in str(error.value)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=f"invalid://user:{private}@postgres/bot")
    assert private not in str(error.value)
