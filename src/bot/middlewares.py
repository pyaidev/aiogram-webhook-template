from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from bot.config import Settings
from bot.db.repositories import upsert_user
from bot.services.rate_limit import RateLimiter


class UserContextMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable[..., Awaitable[Any]], event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None:
            settings: Settings = data["settings"]
            limiter: RateLimiter = data["rate_limiter"]
            if not data.get("is_retry", False):
                allowed, _ = await limiter.check(
                    f"user:{user.id}",
                    limit=settings.user_rate_limit,
                    window=settings.user_rate_window,
                )
                if not allowed:
                    # Deliberately send no reply: spam must not create outbound amplification.
                    return None
            data["db_user"] = await upsert_user(data["session"], user)
        return await handler(event, data)
