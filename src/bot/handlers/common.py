from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db.models import TelegramUser
from bot.db.repositories import user_count


class Preferences(StatesGroup):
    language = State()


def build_common_router() -> Router:
    router = Router(name="common")

    @router.message(CommandStart())
    async def start(message: Message, db_user: TelegramUser) -> None:
        await message.answer(
            f"Welcome, <b>{escape(db_user.first_name)}</b>!\n"
            "Use /help to see the available commands."
        )

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            "/start — start the bot\n/profile — your profile\n"
            "/settings — choose a language\n/cancel — cancel the current action"
        )

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Current action cancelled.")

    @router.message(Command("profile"))
    async def profile(message: Message, db_user: TelegramUser) -> None:
        await message.answer(
            f"ID: <code>{db_user.id}</code>\n"
            f"Name: {escape(db_user.first_name)}\n"
            f"Language preference: {escape(db_user.preferred_language)}"
        )

    @router.message(Command("stats"))
    async def stats(message: Message, settings: Settings, session: AsyncSession) -> None:
        if message.from_user is None or message.from_user.id not in settings.admin_ids:
            return
        await message.answer(f"Registered users: {await user_count(session)}")

    @router.message(Command("settings"))
    async def settings_command(message: Message, state: FSMContext) -> None:
        await state.set_state(Preferences.language)
        await message.answer("Send en, uz or ru to save your language preference; /cancel to exit.")

    @router.message(Preferences.language, F.text.in_({"en", "uz", "ru"}))
    async def save_language(message: Message, state: FSMContext, db_user: TelegramUser) -> None:
        db_user.preferred_language = message.text
        await message.answer("Language preference saved. Template responses currently use English.")
        # Retain state when Telegram rejects the response so retries still match this handler.
        await state.clear()

    @router.message(Preferences.language)
    async def invalid_language(message: Message) -> None:
        await message.answer("Choose en, uz or ru, or use /cancel.")

    return router
