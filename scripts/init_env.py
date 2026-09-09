"""Generate local secrets once; never overwrite an existing environment file."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    target = ROOT / ".env"
    database_password = secrets.token_urlsafe(32)
    redis_password = secrets.token_urlsafe(32)
    template = (ROOT / ".env.example").read_text()
    replacements = {
        "WEBHOOK_SECRET=development-only-change-before-deploy": (
            f"WEBHOOK_SECRET={secrets.token_urlsafe(48)}"
        ),
        "bot:bot@postgres": f"bot:{database_password}@postgres",
        "POSTGRES_PASSWORD=bot": f"POSTGRES_PASSWORD={database_password}",
        "development-redis-change-me": redis_password,
        "METRICS_TOKEN=": f"METRICS_TOKEN={secrets.token_urlsafe(48)}",
        "GRAFANA_ADMIN_PASSWORD=change-me": f"GRAFANA_ADMIN_PASSWORD={secrets.token_urlsafe(24)}",
    }
    for old, new in replacements.items():
        template = template.replace(old, new)
    try:
        # Exclusive creation avoids silently rotating credentials for existing volumes.
        with target.open("x") as handle:
            target.chmod(0o600)
            handle.write(template)
    except FileExistsError:
        print(".env already exists; preserved existing values.")
    else:
        print("Generated .env with local secrets. BOT_TOKEN remains empty.")


if __name__ == "__main__":
    main()
