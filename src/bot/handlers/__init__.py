from aiogram import Router

from bot.handlers.common import build_common_router


def build_router() -> Router:
    router = Router(name="root")
    router.include_router(build_common_router())
    return router
