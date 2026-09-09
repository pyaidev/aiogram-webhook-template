import logging
import sys

import structlog

from bot.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        cache_logger_on_first_use=True,
    )
    # Never emit Bot API request URLs (they contain the bot token).
    for name in ("aiohttp.access", "httpx", "httpcore", "aiogram.event"):
        logging.getLogger(name).setLevel(logging.WARNING)
    if settings.sentry_dsn.get_secret_value():
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn.get_secret_value(),
            environment=settings.environment,
            release=settings.release,
            send_default_pii=False,
            traces_sample_rate=0,
            before_send=_scrub_sentry,
        )


def _scrub_sentry(event: dict, hint: dict) -> dict:
    event.pop("request", None)
    event.pop("breadcrumbs", None)
    event.pop("extra", None)
    for exception in event.get("exception", {}).get("values", []):
        exception["value"] = "redacted; inspect structured error type and update_id"
        for frame in exception.get("stacktrace", {}).get("frames", []):
            frame.pop("vars", None)
    return event
