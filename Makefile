.PHONY: init install up bot monitoring down logs test test-docker lint format migrate backup

init:
	python3 scripts/init_env.py
install:
	uv sync --frozen
up:
	docker compose up -d --build
bot:
	docker compose --profile bot up -d --build
monitoring:
	docker compose --profile monitoring up -d --build
down:
	docker compose --profile bot --profile monitoring down
logs:
	docker compose logs -f --tail=100 app worker
test:
	uv run --frozen pytest -q
test-docker:
	docker compose --profile test build tests
	docker compose --profile test run --rm tests
lint:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
format:
	uv run --frozen ruff check --fix .
	uv run --frozen ruff format .
migrate:
	docker compose run --rm migrate
backup:
	mkdir -p backups
	docker compose exec -T postgres sh -c 'pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -Fc' > backups/bot-$$(date +%Y%m%d-%H%M%S).dump
