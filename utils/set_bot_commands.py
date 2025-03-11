from aiogram import types

from loader import bot
from aiogram.types import BotCommandScopeDefault, BotCommandScopeChat

async def set_default_commands():
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Start the bot"),
            types.BotCommand(command="help", description="Get help information"),
            types.BotCommand(command="auth", description="Login or register")
        ],
        scope=BotCommandScopeDefault()
    )

# Функция установки расширенных команд (для авторизованных пользователей)
async def set_authorized_commands(chat_id: int):
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Restart the bot"),
            types.BotCommand(command="help", description="Get help information"),
            types.BotCommand(command="connect", description="Connect Services"),
        ],
        scope=BotCommandScopeChat(chat_id=chat_id)
    )
