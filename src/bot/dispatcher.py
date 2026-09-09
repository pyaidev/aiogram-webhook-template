from aiogram import Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import Settings
from bot.handlers import build_router
from bot.middlewares import UserContextMiddleware
from bot.services.rate_limit import RateLimiter


def build_dispatcher(settings: Settings, redis: Redis) -> Dispatcher:
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(prefix="bot:fsm", with_bot_id=True),
        state_ttl=86400,
        data_ttl=86400,
    )
    dispatcher = Dispatcher(
        storage=storage,
        events_isolation=storage.create_isolation(
            lock_kwargs={"timeout": settings.worker_timeout_seconds + 15}
        ),
        settings=settings,
        rate_limiter=RateLimiter(redis),
    )
    dispatcher.update.outer_middleware(UserContextMiddleware())
    dispatcher.include_router(build_router())
    return dispatcher
