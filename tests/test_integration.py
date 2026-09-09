import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SendMessage
from sqlalchemy import func, select

from bot.db.models import InboxUpdate, TelegramUser
from bot.db.repositories import enqueue_update
from bot.dispatcher import build_dispatcher
from bot.handlers.common import Preferences
from bot.web import create_app
from bot.worker import process_one

pytestmark = pytest.mark.integration


async def test_webhook_commits_and_deduplicates(aiohttp_client, infrastructure, telegram_update):
    settings = infrastructure["settings"]
    client = await aiohttp_client(create_app(settings, resources=infrastructure))
    for _ in range(2):
        response = await client.post(
            settings.webhook_path,
            json=telegram_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret.get_secret_value()},
        )
        assert response.status == 200
    async with infrastructure["sessions"]() as session:
        assert await session.scalar(select(func.count()).select_from(InboxUpdate)) == 1
        item = await session.get(InboxUpdate, telegram_update["update_id"])
        assert item.payload == telegram_update


async def test_readiness_and_queue_metrics(aiohttp_client, infrastructure, telegram_update):
    async with infrastructure["sessions"].begin() as session:
        await enqueue_update(session, telegram_update)
    client = await aiohttp_client(create_app(infrastructure["settings"], resources=infrastructure))
    assert (await client.get("/health/ready/")).status == 200
    response = await client.get("/metrics")
    assert response.status == 200
    assert 'bot_inbox_updates{status="pending"} 1.0' in await response.text()


async def test_atomic_redis_limit_under_concurrency(infrastructure):
    results = await asyncio.gather(
        *[infrastructure["limiter"].check("integration", limit=7, window=10) for _ in range(30)]
    )
    assert sum(allowed for allowed, _ in results) == 7
    assert await infrastructure["redis"].ttl("bot:rate:integration") > 0


async def test_successful_worker_clears_payload(infrastructure, telegram_update):
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    dispatcher = AsyncMock()
    assert await process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    async with sessions() as session:
        item = await session.get(InboxUpdate, telegram_update["update_id"])
        assert item.status == "done"
        assert item.payload == {}
        assert item.completed_at is not None
    assert not await process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    assert dispatcher.feed_update.await_count == 1


async def test_worker_retries_and_rolls_back_handler_db_effects(infrastructure, telegram_update):
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)

    async def broken_handler(bot, update, session, **kwargs):
        session.add(TelegramUser(id=99, first_name="rollback"))
        await session.flush()
        raise RuntimeError("private-payload-must-not-be-stored")

    dispatcher = AsyncMock()
    dispatcher.feed_update.side_effect = broken_handler
    assert await process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    async with sessions() as session:
        item = await session.get(InboxUpdate, telegram_update["update_id"])
        assert item.status == "pending"
        assert item.attempts == 1
        assert item.available_at > datetime.now(UTC)
        assert item.last_error == "RuntimeError"
        assert await session.get(TelegramUser, 99) is None


async def test_worker_moves_exhausted_update_to_dead_letters(infrastructure, telegram_update):
    settings = infrastructure["settings"].model_copy(update={"worker_max_attempts": 1})
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    dispatcher = AsyncMock()
    dispatcher.feed_update.side_effect = ValueError("invalid")
    await process_one(sessions, dispatcher, AsyncMock(), settings)
    async with sessions() as session:
        item = await session.get(InboxUpdate, telegram_update["update_id"])
        assert item.status == "failed"
        assert item.completed_at is not None
        assert item.payload == telegram_update


async def test_telegram_retry_after_is_respected(infrastructure, telegram_update):
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    dispatcher = AsyncMock()
    dispatcher.feed_update.side_effect = TelegramRetryAfter(
        method=SendMessage(chat_id=42, text="hello"), message="Retry", retry_after=60
    )
    await process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    async with sessions() as session:
        item = await session.get(InboxUpdate, telegram_update["update_id"])
        assert item.available_at > datetime.now(UTC) + timedelta(seconds=55)


async def test_concurrent_workers_do_not_process_same_update(infrastructure, telegram_update):
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(*args, **kwargs):
        entered.set()
        await release.wait()

    dispatcher = AsyncMock()
    dispatcher.feed_update.side_effect = handler
    task = asyncio.create_task(
        process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    )
    await asyncio.wait_for(entered.wait(), 5)
    assert not await process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    release.set()
    assert await task
    assert dispatcher.feed_update.await_count == 1


async def test_real_dispatcher_start_escapes_name_and_persists_user(
    infrastructure, telegram_update
):
    settings = infrastructure["settings"]
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    dispatcher = build_dispatcher(settings, infrastructure["redis"])
    bot = Bot(
        token="123456:FAKE_OFFLINE_TOKEN", default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    bot.session = AsyncMock()
    try:
        await process_one(sessions, dispatcher, bot, settings)
        sent_method = bot.session.call_args.args[1]
        assert "&lt;Alice&gt;" in sent_method.text
        async with sessions() as session:
            assert (await session.get(TelegramUser, 42)).username == "alice"
            assert (await session.get(InboxUpdate, telegram_update["update_id"])).status == "done"
    finally:
        await dispatcher.storage.close()
        await dispatcher.fsm.events_isolation.close()
        await bot.session.close()


async def test_fsm_and_admission_survive_telegram_retry(infrastructure, telegram_update):
    settings = infrastructure["settings"].model_copy(update={"user_rate_limit": 1})
    sessions = infrastructure["sessions"]
    telegram_update["message"]["text"] = "uz"
    telegram_update["message"]["entities"] = []
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    dispatcher = build_dispatcher(settings, infrastructure["redis"])
    bot = Bot(token="123456:FAKE_OFFLINE_TOKEN")
    bot.session = AsyncMock()
    state = dispatcher.fsm.get_context(bot=bot, chat_id=42, user_id=42)
    await state.set_state(Preferences.language)
    bot.session.side_effect = TelegramRetryAfter(
        method=SendMessage(chat_id=42, text="saved"), message="Retry", retry_after=60
    )
    try:
        await process_one(sessions, dispatcher, bot, settings)
        assert await state.get_state() == Preferences.language.state
        async with sessions.begin() as session:
            assert await session.get(TelegramUser, 42) is None
            item = await session.get(InboxUpdate, telegram_update["update_id"])
            assert item.attempts == 1
            item.available_at = datetime.now(UTC) - timedelta(seconds=1)
        bot.session.side_effect = None
        await process_one(sessions, dispatcher, bot, settings)
        assert bot.session.await_count == 2
        assert await state.get_state() is None
        async with sessions() as session:
            assert (await session.get(TelegramUser, 42)).preferred_language == "uz"
            assert (await session.get(InboxUpdate, telegram_update["update_id"])).status == "done"
    finally:
        await state.clear()
        await dispatcher.storage.close()
        await dispatcher.fsm.events_isolation.close()
        await bot.session.close()


async def test_cancelled_worker_releases_row_for_recovery(infrastructure, telegram_update):
    sessions = infrastructure["sessions"]
    async with sessions.begin() as session:
        await enqueue_update(session, telegram_update)
    entered = asyncio.Event()

    async def handler(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    dispatcher = AsyncMock()
    dispatcher.feed_update.side_effect = handler
    task = asyncio.create_task(
        process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    )
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    dispatcher.feed_update.side_effect = None
    assert await process_one(sessions, dispatcher, AsyncMock(), infrastructure["settings"])
    async with sessions() as session:
        assert (await session.get(InboxUpdate, telegram_update["update_id"])).status == "done"
