import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiohttp import web
from sqlalchemy import delete, update

from bot.config import Settings
from bot.db.models import InboxUpdate
from bot.db.session import make_engine, make_sessions
from bot.handlers import build_router
from bot.logging import configure_logging
from bot.web import create_app
from bot.worker import run_worker


async def manage(settings: Settings, command: str, update_id: int | None) -> None:
    if command in {"set-webhook", "webhook-info", "delete-webhook"}:
        async with Bot(token=settings.require_bot_token()) as bot:
            if command == "set-webhook":
                if not settings.webhook_url:
                    raise ValueError("Set WEBHOOK_URL before registering the webhook")
                await bot.set_webhook(
                    url=settings.webhook_url,
                    secret_token=settings.webhook_secret.get_secret_value(),
                    allowed_updates=build_router().resolve_used_update_types(),
                    drop_pending_updates=False,
                )
                print("Webhook registered; pending updates preserved.")
            elif command == "delete-webhook":
                await bot.delete_webhook(drop_pending_updates=False)
                print("Webhook removed; pending updates preserved.")
            else:
                info = await bot.get_webhook_info()
                print(f"Configured: {bool(info.url)}; pending updates: {info.pending_update_count}")
        return
    engine = make_engine(settings)
    try:
        async with make_sessions(engine).begin() as session:
            if command == "retry-update":
                result = await session.execute(
                    update(InboxUpdate)
                    .where(InboxUpdate.update_id == update_id, InboxUpdate.status == "failed")
                    .values(
                        status="pending",
                        attempts=0,
                        available_at=datetime.now(UTC),
                        completed_at=None,
                        last_error=None,
                    )
                )
                print(f"Requeued {result.rowcount} failed update(s).")
            else:
                cutoff = datetime.now(UTC) - timedelta(days=settings.inbox_retention_days)
                result = await session.execute(
                    delete(InboxUpdate).where(
                        InboxUpdate.status == "done", InboxUpdate.completed_at < cutoff
                    )
                )
                print(f"Removed {result.rowcount} expired completed update(s).")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Aiogram webhook service and inbox worker")
    parser.add_argument(
        "command",
        choices=[
            "serve",
            "worker",
            "set-webhook",
            "webhook-info",
            "delete-webhook",
            "retry-update",
            "cleanup-inbox",
        ],
        nargs="?",
        default="serve",
    )
    parser.add_argument("--update-id", type=int)
    args = parser.parse_args()
    if args.command == "retry-update" and args.update_id is None:
        parser.error("retry-update requires --update-id")
    settings = Settings()
    configure_logging(settings)
    if args.command == "serve":
        web.run_app(create_app(settings), host=settings.host, port=settings.port, access_log=None)
    elif args.command == "worker":
        asyncio.run(run_worker(settings))
    else:
        asyncio.run(manage(settings, args.command, args.update_id))


if __name__ == "__main__":
    main()
