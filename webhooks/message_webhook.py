from aiohttp import web
from aiogram import Bot
from data.config import BOT_TOKEN
import json
import logging
from utils.db import get_user_tokens
from aiogram.enums import ChatAction

# Set up logging
logger = logging.getLogger(__name__)

# Initialize bot instance
bot = Bot(token=BOT_TOKEN)

