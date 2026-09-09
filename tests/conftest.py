import os
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete

from bot.config import Settings
from bot.db.models import InboxUpdate, TelegramUser
from bot.db.session import make_engine, make_sessions
from bot.services.rate_limit import RateLimiter


@pytest.fixture
def settings():
    return Settings(_env_file=None, environment="test")


@pytest.fixture
def fake_resources():
    limiter = AsyncMock()
    limiter.check.return_value = (True, 1)
    return {"limiter": limiter, "redis": AsyncMock(), "sessions": AsyncMock()}


@pytest.fixture
async def infrastructure():
    database_url = os.getenv("TEST_DATABASE_URL")
    redis_url = os.getenv("TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("Set TEST_DATABASE_URL and TEST_REDIS_URL for integration tests")
    if not urlsplit(database_url).path.endswith("_test"):
        pytest.fail("Refusing integration database cleanup: database name must end with _test")
    settings = Settings(
        _env_file=None, environment="test", database_url=database_url, redis_url=redis_url
    )
    engine = make_engine(settings)
    redis = Redis.from_url(redis_url, socket_timeout=3)
    sessions = make_sessions(engine)
    async with sessions.begin() as session:
        await session.execute(delete(InboxUpdate))
        await session.execute(delete(TelegramUser))
    await redis.delete("bot:rate:ingress", "bot:rate:user:42", "bot:rate:integration")
    yield {
        "settings": settings,
        "engine": engine,
        "redis": redis,
        "sessions": sessions,
        "limiter": RateLimiter(redis),
    }
    await redis.aclose()
    await engine.dispose()


@pytest.fixture
def telegram_update():
    return {
        "update_id": 10001,
        "message": {
            "message_id": 1,
            "date": 1750000000,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 42, "is_bot": False, "first_name": "<Alice>", "username": "alice"},
            "text": "/start",
            "entities": [{"type": "bot_command", "offset": 0, "length": 6}],
        },
    }
