from aiogram.types import User
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import InboxUpdate, TelegramUser


async def enqueue_update(session: AsyncSession, payload: dict) -> bool:
    statement = (
        insert(InboxUpdate)
        .values(update_id=payload["update_id"], payload=payload)
        .on_conflict_do_nothing(index_elements=[InboxUpdate.update_id])
        .returning(InboxUpdate.update_id)
    )
    return (await session.scalar(statement)) is not None


async def upsert_user(session: AsyncSession, telegram_user: User) -> TelegramUser:
    statement = insert(TelegramUser).values(
        id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        language_code=telegram_user.language_code,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[TelegramUser.id],
        set_={
            "username": statement.excluded.username,
            "first_name": statement.excluded.first_name,
            "language_code": statement.excluded.language_code,
            "updated_at": func.now(),
        },
    ).returning(TelegramUser)
    return (await session.scalars(statement)).one()


async def user_count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(TelegramUser)) or 0)
