from aiogram import types
from aiogram.filters import Command

from loader import dp


@dp.message(Command("help"))
async def bot_help(message: types.Message):
    help_text = (
        "🎯 Available Commands:\n\n"
        "🚀 /start - Start the bot\n"
        "🔐 /auth - Login or Register\n"
        "❓ /help - Show this help message\n\n"
        "💡 Tips:\n"
        "• Send text messages to chat with AI\n"
        "• Send voice messages for voice recognition\n"
        "• Use commands with / prefix"
    )
    await message.answer(help_text)
