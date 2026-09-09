import asyncio
import signal
from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Update
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import Settings
from bot.db.models import InboxUpdate
from bot.db.session import make_engine, make_sessions
from bot.dispatcher import build_dispatcher

log = structlog.get_logger()


async def process_one(
    sessions: async_sessionmaker, dispatcher, bot: Bot, settings: Settings
) -> bool:
    """Lock one item through dispatch; a process crash rolls back and releases its lock.

    PostgreSQL effects use a savepoint. Telegram sends and Redis FSM changes cannot be
    rolled back: processing is at-least-once, never an exactly-once delivery guarantee.
    """
    async with sessions.begin() as session:
        item = await session.scalar(
            select(InboxUpdate)
            .where(InboxUpdate.status == "pending", InboxUpdate.available_at <= func.now())
            .order_by(InboxUpdate.update_id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item is None:
            return False
        structlog.contextvars.bind_contextvars(update_id=item.update_id)
        try:
            try:
                async with session.begin_nested(), asyncio.timeout(settings.worker_timeout_seconds):
                    update = Update.model_validate(item.payload, context={"bot": bot})
                    await dispatcher.feed_update(
                        bot, update, session=session, is_retry=item.attempts > 0
                    )
            except Exception as exc:
                item.attempts += 1
                item.last_error = type(exc).__name__
                if item.attempts >= settings.worker_max_attempts:
                    item.status = "failed"
                    item.completed_at = datetime.now(UTC)
                else:
                    delay = (
                        exc.retry_after
                        if isinstance(exc, TelegramRetryAfter)
                        else min(2**item.attempts, 300)
                    )
                    item.available_at = datetime.now(UTC) + timedelta(seconds=delay)
                log.warning(
                    "update_processing_failed",
                    error_type=item.last_error,
                    attempt=item.attempts,
                    status=item.status,
                )
                if settings.sentry_dsn.get_secret_value():
                    import sentry_sdk

                    sentry_sdk.capture_exception(exc)
            else:
                item.status = "done"
                item.completed_at = datetime.now(UTC)
                item.last_error = None
                # Remove successful update payloads promptly; retain the ID for deduplication.
                item.payload = {}
                log.info("update_processed")
        finally:
            structlog.contextvars.clear_contextvars()
    return True


async def run_worker(settings: Settings) -> None:
    bot = Bot(
        token=settings.require_bot_token(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = make_engine(settings)
    redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=3)
    dispatcher = build_dispatcher(settings, redis)
    sessions = make_sessions(engine)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)
    log.info("worker_started")
    try:
        while not stopping.is_set():
            try:
                worked = await process_one(sessions, dispatcher, bot, settings)
            except Exception as exc:
                log.error("worker_dependency_failed", error_type=type(exc).__name__)
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=settings.worker_poll_seconds)
                except TimeoutError:
                    pass
    finally:
        await dispatcher.storage.close()
        await dispatcher.fsm.events_isolation.close()
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()
        log.info("worker_stopped")
