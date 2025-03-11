
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Router
router = Router()


@router.message()
async def handle_unauthorized(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None and not message.text.startswith('/'):
        await message.answer(
            "🔒 Please login first\n⚡️ Use /auth to get started"
        )