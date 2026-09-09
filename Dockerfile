FROM ghcr.io/astral-sh/uv:0.11.1 AS uv
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable && \
    groupadd --gid 10001 bot && useradd --uid 10001 --gid bot --create-home bot && \
    chown -R bot:bot /app

FROM base AS test
COPY tests ./tests
RUN uv sync --frozen
USER bot
CMD ["pytest", "-q"]

FROM base AS runtime
USER bot
EXPOSE 8000
CMD ["python", "-m", "bot", "serve"]
