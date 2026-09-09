import pytest

from bot.web import create_app


async def test_liveness_is_independent_of_dependencies(aiohttp_client, settings, fake_resources):
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.get("/health/live/")
    assert response.status == 200
    assert await response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("secret", [None, "wrong"])
async def test_webhook_requires_secret(aiohttp_client, settings, fake_resources, secret):
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
    response = await client.post(settings.webhook_path, json={"update_id": 1}, headers=headers)
    assert response.status == 401
    fake_resources["limiter"].check.assert_not_called()


async def test_metrics_requires_bearer_token(aiohttp_client, settings, fake_resources):
    settings = settings.model_copy(update={"metrics_token": type(settings.metrics_token)("m" * 40)})
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.get("/metrics")
    assert response.status == 401


async def test_json_content_type_required(aiohttp_client, settings, fake_resources):
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.post(
        settings.webhook_path,
        data="not-json",
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret.get_secret_value()},
    )
    assert response.status == 415


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"update_id": -1},
        {"update_id": True},
        {"update_id": "1"},
        {"update_id": 1, "message": {}},
    ],
)
async def test_invalid_updates_rejected(aiohttp_client, settings, fake_resources, payload):
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.post(
        settings.webhook_path,
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret.get_secret_value()},
    )
    assert response.status == 400


async def test_oversized_body_rejected(aiohttp_client, settings, fake_resources):
    settings = settings.model_copy(update={"max_body_bytes": 1024})
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.post(
        settings.webhook_path,
        json={"update_id": 1, "padding": "x" * 2048},
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret.get_secret_value()},
    )
    assert response.status == 413


async def test_ingress_rate_limit_includes_retry_after(aiohttp_client, settings, fake_resources):
    fake_resources["limiter"].check.return_value = (False, 9)
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.post(
        settings.webhook_path,
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret.get_secret_value()},
    )
    assert response.status == 429
    assert response.headers["Retry-After"] == "9"


async def test_redis_error_fails_closed_without_leaking_error(
    aiohttp_client, settings, fake_resources
):
    fake_resources["limiter"].check.side_effect = RuntimeError("redis://secret:password@host")
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.post(
        settings.webhook_path,
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret.get_secret_value()},
    )
    assert response.status == 503
    assert "password" not in await response.text()


async def test_readiness_fails_when_redis_down(aiohttp_client, settings, fake_resources):
    fake_resources["redis"].ping.side_effect = ConnectionError()
    client = await aiohttp_client(create_app(settings, resources=fake_resources))
    response = await client.get("/health/ready/")
    assert response.status == 503
