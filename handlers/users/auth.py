from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from states.state import BotStates
from handlers.users.start import KeyboardFactory
from aiogram import Router
router = Router()

# Authorization Flow
@router.message(Command("auth"))
async def bot_auth(message: Message, state: FSMContext):
    await message.answer(
        "Would you like to login or sign up?",
        reply_markup=KeyboardFactory.auth_keyboard()
    )
    await state.set_state(BotStates.choosing_auth_type)