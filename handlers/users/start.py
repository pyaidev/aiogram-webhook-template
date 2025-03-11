from aiogram import Router, types
from aiogram.filters import CommandStart

router = Router()

@router.message(CommandStart())
async def bot_start(message: types.Message):
    welcome_text = (
        f"👋 Welcome, {message.from_user.full_name}!\n\n"
        "🤖 I'm your AI Assistant, ready to help you with:\n"
        "• 💭 Chat and answer questions\n"
        "• 🗣 Voice message recognition\n"
        "• 📅 Services integration\n\n"
        "🔑 Use /auth to get started!\n"
        "❓ Use /help for all available commands"
    )
    await message.answer(welcome_text)