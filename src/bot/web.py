import asyncio
import json
import secrets
from collections.abc import Awaitable, Callable
from time import perf_counter

import structlog
from aiogram.types import Update
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import func, select, text

from bot.config import Settings
from bot.db.models import InboxUpdate
from bot.db.repositories import enqueue_update
from bot.db.session import make_engine, make_sessions
from bot.metrics import Metrics
from bot.services.rate_limit import RateLimiter

log = structlog.get_logger()
SETTINGS = web.AppKey("settings", Settings)
METRICS = web.AppKey("metrics", Metrics)
RESOURCES = web.AppKey("resources", dict)


@web.middleware
async def request_context(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    request_id = secrets.token_hex(12)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started = perf_counter()
    status = 500
    try:
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.json_response({"error": exc.reason}, status=exc.status)
            if "Retry-After" in exc.headers:
                response.headers["Retry-After"] = exc.headers["Retry-After"]
        except Exception as exc:
            # Exception strings may contain DB credentials or Telegram payloads.
            log.error("http_request_failed", error_type=type(exc).__name__)
            response = web.json_response({"error": "Service unavailable"}, status=503)
        status = response.status
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        route = request.match_info.route.name or "unmatched"
        metrics = request.app[METRICS]
        metrics.requests.labels(route, str(status)).inc()
        metrics.duration.labels(route).observe(perf_counter() - started)
        structlog.contextvars.clear_contextvars()


async def live(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def ready(request: web.Request) -> web.Response:
    resources = request.app[RESOURCES]
    try:
        async with asyncio.timeout(3):
            await resources["redis"].ping()
            async with resources["sessions"]() as session:
                await session.execute(text("SELECT update_id FROM inbox_updates LIMIT 1"))
    except Exception:
        return web.json_response({"status": "unavailable"}, status=503)
    return web.json_response({"status": "ready"})


async def webhook(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS]
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(
        supplied.encode(), settings.webhook_secret.get_secret_value().encode()
    ):
        raise web.HTTPUnauthorized()
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType()
    resources = request.app[RESOURCES]
    allowed, retry_after = await resources["limiter"].check(
        "ingress", limit=settings.ingress_rate_limit, window=settings.ingress_rate_window
    )
    if not allowed:
        raise web.HTTPTooManyRequests(headers={"Retry-After": str(retry_after)})
    try:
        payload = await request.json()
        if not isinstance(payload, dict) or type(payload.get("update_id")) is not int:
            raise ValueError("update_id must be an integer")
        update = Update.model_validate(payload)
        if update.update_id < 0:
            raise ValueError("Negative update ID")
    except (json.JSONDecodeError, ValidationError, ValueError, UnicodeDecodeError):
        raise web.HTTPBadRequest(reason="Invalid Telegram update") from None
    async with resources["sessions"].begin() as session:
        inserted = await enqueue_update(session, payload)
    request.app[METRICS].accepted.labels("new" if inserted else "duplicate").inc()
    # Acknowledgement is sent only AFTER the PostgreSQL transaction commits.
    return web.json_response({"ok": True})


async def metrics_endpoint(request: web.Request) -> web.Response:
    expected = request.app[SETTINGS].metrics_token.get_secret_value()
    supplied = request.headers.get("Authorization", "")
    if expected and not secrets.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
        raise web.HTTPUnauthorized()
    registry = request.app[METRICS].registry
    queue_registry = type(registry)()
    queue = Gauge("bot_inbox_updates", "Durable inbox depth", ["status"], registry=queue_registry)
    oldest = Gauge(
        "bot_inbox_oldest_pending_seconds", "Oldest pending update age", registry=queue_registry
    )
    async with asyncio.timeout(3):
        async with request.app[RESOURCES]["sessions"]() as session:
            rows = await session.execute(
                select(InboxUpdate.status, func.count()).group_by(InboxUpdate.status)
            )
            counts = dict(rows.all())
            for status in ("pending", "done", "failed"):
                queue.labels(status).set(counts.get(status, 0))
            age = await session.scalar(
                select(func.extract("epoch", func.now() - func.min(InboxUpdate.created_at))).where(
                    InboxUpdate.status == "pending"
                )
            )
            oldest.set(max(float(age or 0), 0))
    return web.Response(
        body=generate_latest(registry) + generate_latest(queue_registry),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


def create_app(
    settings: Settings | None = None, *, resources: dict | None = None
) -> web.Application:
    settings = settings or Settings()
    app = web.Application(middlewares=[request_context], client_max_size=settings.max_body_bytes)
    app[SETTINGS] = settings
    app[METRICS] = Metrics()

    async def lifespan(application: web.Application):
        engine = make_engine(settings)
        redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=3)
        application[RESOURCES] = {
            "engine": engine,
            "sessions": make_sessions(engine),
            "redis": redis,
            "limiter": RateLimiter(redis),
        }
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    if resources is None:
        app.cleanup_ctx.append(lifespan)
    else:
        app[RESOURCES] = resources
    app.router.add_get("/health/live/", live, name="health_live")
    app.router.add_get("/health/ready/", ready, name="health_ready")
    app.router.add_get("/metrics", metrics_endpoint, name="metrics")
    app.router.add_post(settings.webhook_path, webhook, name="telegram_webhook")
    return app
