# Deployment and recovery

Set `ENVIRONMENT=production`, a generated `WEBHOOK_SECRET`, a full HTTPS `WEBHOOK_URL`, generated
`METRICS_TOKEN`, non-default PostgreSQL password, authenticated Redis URL and a real `BOT_TOKEN`
for workers. Production settings reject missing/default infrastructure secrets. The ingestion service
does not require the bot token; the worker and Telegram management commands do.

Terminate TLS at a trusted reverse proxy. Publish only `/telegram/webhook` to Telegram. Keep metrics,
readiness, PostgreSQL, Redis, Prometheus and Grafana private. Compose binds public development ports
to `127.0.0.1`; on another Docker host/network adapt the reverse proxy route intentionally. Example
Nginx location inside your TLS server (TLS certificates/domain are deployment-specific):

```nginx
location = /telegram/webhook {
    client_max_body_size 1m;
    proxy_pass http://127.0.0.1:8003;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 5s;
    proxy_read_timeout 15s;
}
```

Do not put the bot token or webhook secret into URLs. Reverse proxies must preserve
`X-Telegram-Bot-Api-Secret-Token`. The application authenticates this header; do not trust arbitrary
`X-Forwarded-For` values for authentication. Apply volumetric/WAF limits at the edge in addition to
the application limits. `INGRESS_RATE_LIMIT` is bot-global so proxies cannot bypass it with fake IPs.

Start `docker compose --profile bot --profile monitoring up -d --build`. The migration service must
finish successfully before app/worker start. For orchestration beyond Compose, run migration as a
single release job. Ensure the previous release can read the new schema; use expand/contract changes.

`set-webhook` is an explicit deployment command after checking HTTPS and readiness. It preserves
pending updates. Never set/delete the webhook during every replica startup/shutdown.

## Backup

```bash
make backup
```

This creates a PostgreSQL custom-format dump in ignored `backups/`. Copy encrypted backups to
separate storage, with retention and restore drills. A local dump alone is not disaster recovery.
Redis AOF is enabled, but Redis restart may lose recent FSM writes depending on fsync policy.

## Restore drill into a separate database

Validate a specific backup path before using it. The following creates a separate scratch database
and restores without changing the active `bot` database. Never restore over the live database before
testing and arranging downtime.

```bash
docker compose exec postgres createdb -U bot bot_restore_check
docker compose exec -T postgres pg_restore -U bot -d bot_restore_check --exit-on-error < backups/EXACT_BACKUP.dump
docker compose exec postgres psql -U bot -d bot_restore_check -c 'SELECT count(*) FROM telegram_users;'
```

When the drill is reviewed, the scratch database can be dropped explicitly. For real recovery, stop
workers and ingestion, restore into a new database, point `DATABASE_URL` to it, apply reviewed forward
migrations, start the stack, check readiness and backlog, then reopen ingress. Do not use `down -v`:
that deletes persistent PostgreSQL/Redis/monitoring volumes.

## Failed updates

Inspect only necessary fields from `inbox_updates`: ID, status, attempts, error type. Payloads can
contain personal data. Resolve the failure, then run `python -m bot retry-update --update-id ID`.
The command only resets failed updates; it never resends completed updates. External sends may have
already happened before failure; verify business idempotency before retrying sensitive actions.

Schedule `python -m bot cleanup-inbox` daily. It only deletes successful rows older than retention;
pending and failed rows remain. Configure a separate human-reviewed retention process for failed
payloads. Monitor queue age, failed rows and dependency health. Alert rules are provisioned, but
notification delivery requires an Alertmanager and your chosen receiver configuration.

## Scaling and resources

Run one worker initially. `docker compose --profile bot up -d --scale worker=2` is supported by the
database queue, with the ordering caveats in architecture.md. Keep a distinct Compose project and
database per bot. For high traffic, partition by chat and consider a dedicated durable broker when
workload measurements justify it. Redis uses `noeviction`: exhaustion fails visibly instead of silently
evicting FSM and rate-limit keys. Set host/container memory budgets after measuring production usage.

Update locked dependencies and base image versions regularly; Dependabot proposes uv, Docker and
GitHub Actions changes. Verify advisory scanners and image digests in your deployment pipeline.
Sentry is optional and scrubbed; do not add raw message payloads, token URLs or local variables to logs.
