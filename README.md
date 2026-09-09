# Aiogram Webhook Boilerplate

Katta loyihalar uchun modulli Telegram bot asosi: **aiogram 3, aiohttp, PostgreSQL,
SQLAlchemy async, Alembic, Redis FSM, Docker, Prometheus va Grafana**.

Webhook yangilanishni bazaga yozib, transaction tugagach Telegram'ga `200` qaytaradi.
Alohida worker update'larni qayta ishlaydi; process to'xtasa update navbatda qoladi.
Bot tokeni URL yoki loglarda ishlatilmaydi. Telegram webhook'i avtomatik o'rnatilmaydi
yoki o'chirilmaydi; pending update'lar tashlab yuborilmaydi.

## Tez boshlash — Docker

Python 3 faqat `.env` yaratish uchun kerak; app va dependencies Docker ichida ishlaydi.

```bash
git clone https://github.com/pyaidev/aiogram-webhook-template.git
cd aiogram-webhook-template
make init
make up
make monitoring
curl --fail http://127.0.0.1:8003/health/ready/
```

`make init` tasodifiy PostgreSQL, Redis, webhook, metrics va Grafana secretlarini
`.env` ga yozadi (`0600`); mavjud faylni o'zgartirmaydi. `.env` Git yoki Docker image'ga kirmaydi.
PostgreSQL/Redis uchun host portlari ochilmaydi. Named volumes ishlatiladi; Desktop
papkasini Docker bilan ulash talab qilinmaydi.

| Xizmat | Manzil |
| --- | --- |
| Liveness | http://127.0.0.1:8003/health/live/ |
| Readiness: DB schema + Redis | http://127.0.0.1:8003/health/ready/ |
| Telegram webhook | http://127.0.0.1:8003/telegram/webhook |
| Grafana | http://127.0.0.1:3002/ |
| Prometheus | http://127.0.0.1:9092/ |

Grafana foydalanuvchisi `admin`; parol `.env` dagi `GRAFANA_ADMIN_PASSWORD`.
Monitoring alohida `monitoring` profilida. Default `make up` Telegram bilan aloqaga chiqmaydi;
token bo'lmasa health, persistence va offline testlar ishlaydi, xabarlar qayta ishlanmaydi.

## Haqiqiy botni ulash

1. BotFather tokenini `.env` dagi `BOT_TOKEN` ga kiriting.
2. Reverse proxy orqali app'ga haqiqiy HTTPS domen ulang. Faqat webhook path'ini ommaga oching.
3. `.env` dagi `WEBHOOK_URL=https://bot.example.com/telegram/webhook` ni sozlang.
4. `make bot` worker'ni ishga tushiradi.
5. Webhook tayyor bo'lgach, faqat bir marta quyidagi boshqaruv buyrug'ini bajaring:

```bash
docker compose run --rm app python -m bot set-webhook
docker compose run --rm app python -m bot webhook-info
```

Bu buyruqlar Telegram API'ga murojaat qiladi. `delete-webhook` ham explicit buyruq;
shutdown paytida webhook o'chirilmaydi. Rolling deploy boshqa instance webhook'ini uzmaydi.
Token almashtirilsa bot uchun alohida DB/Redis namespace ishlating: bu template bitta botga mo'ljallangan.

Mavjud namunaviy komandalar: `/start`, `/help`, `/profile`, `/settings`, `/cancel`.
`/stats` faqat `.env` dagi `ADMIN_IDS=[123456789]` ro'yxatiga ochiq.
`/settings` Redis FSM orqali `en`, `uz`, `ru` afzalligini saqlaydi; namunaviy javoblar
hozircha inglizcha. Matnga kiritilgan ism HTML escape qilinadi.

## Fayl strukturasi

```text
src/bot/
  __main__.py           # serve / worker / Telegram management CLI
  config.py             # typed environment + production validation
  web.py                # webhook ingestion, health, protected metrics
  dispatcher.py         # router, middleware, Redis FSM wiring
  worker.py             # durable inbox processing, retry/dead letters
  handlers/             # Telegram transport; thin command handlers
  services/             # business operations, atomic Redis rate limiter
  db/
    models.py           # SQLAlchemy models
    repositories.py     # PostgreSQL data operations
    session.py          # engine and transaction lifecycle
  middlewares.py        # user context and per-user throttling
  logging.py            # structured logs + optional Sentry
migrations/             # Alembic version history
tests/                  # offline and real PostgreSQL/Redis integration tests
monitoring/             # image-baked config, dashboard and alert rules
docs/                   # architecture, deployment and recovery
scripts/                # local setup helpers
```

Yangi domain uchun `handlers/orders.py`, `services/orders.py` va tegishli DB models/repositories
qo'shing. Domain kattalashganda `features/orders/{handlers,service,repository}.py` ko'rinishiga
o'tkazish mumkin; dastlab har bir funksiya uchun yangi abstraksiya yaratish shart emas.
Handler ichida to'g'ridan-to'g'ri session yaratmang: worker transaction'i dependency sifatida beriladi.

Eski template'dagi ishlamaydigan auth/calendar/OpenAI demo fragmentlari, duplicate global Bot
instance'lari, SQLite token storage va IDE fayllari olib tashlandi. Oldingi holat Git tarixida saqlangan.
Bu biznes funksiyalar to'liq implementatsiya qilinmagan edi; yangi asos tayyor ishlaydigan komandalarga ega.

## Ishonchlilik va rate limit

- Secret tekshiruvi constant-time; noto'g'ri secret `401`, JSON bo'lmasa `415`, invalid update `400`.
- Maksimal body 1 MiB. Bazaga yozish yoki Redis ishlamasa `503`: Telegram keyin qayta jo'natadi.
- `update_id` unique: Telegram qayta jo'natgan update ikkinchi marta navbatga yozilmaydi.
- PostgreSQL `FOR UPDATE SKIP LOCKED` worker'lar o'rtasida bir update'ni parallel ishlashdan saqlaydi.
- Redis FSM bir bot/chat/user holatini 24 soat saqlaydi; event isolation lock timeout worker timeout'dan uzun.
- Redis Lua atomic rate limit: default har user uchun 10 so'rov/10 soniya; ingress uchun 2000/soniya.
  Fixed window chegara atrofida ikki oynalik burst berishi mumkin. Limitni trafikga qarab sozlang.
- Ingress limit `429` + `Retry-After`. User spam'i worker'da javobsiz tugaydi; qo'shimcha spam-javob yuborilmaydi.
- Worker xatoda exponential retry qiladi, Telegram `retry_after` qiymatini hurmat qiladi; 5 urinishdan keyin `failed`.
- Telegram'ga xabar yuborish va Redis FSM DB transaction'iga kirmaydi: kafolat **at-least-once**, exactly-once emas.
  To'lov/olish-sotish kabi operatsiyalarga alohida business idempotency key kerak.
- Bir nechta worker ishlarni parallel bajarishi mumkin, ammo bitta chatning qat'iy update tartibi kafolatlanmaydi.
  Retry kutayotgan update keyinroq bajarilishi bitta worker'da ham mumkin. Default bitta worker bilan
  boshlang; qat'iy ketma-ketlik kerak bo'lsa chat bo'yicha shard/order talabini alohida loyihalang.

## Testlar va development

```bash
uv sync --frozen
make lint
make test                  # offline tests; integration tests skip without test DB URLs
make test-docker           # dedicated ephemeral PostgreSQL + Redis; real migration/queue tests
```

Dependency versiyalari `uv.lock` da mahkamlangan. `uv lock --upgrade` ni alohida o'zgarish sifatida
testlardan o'tkazib yangilang. Docker `test` stage production image'ga test paketlarini qo'shmaydi.
CI lint, format, offline testlar, real PostgreSQL/Redis testlar, Alembic drift va image build'ni tekshiradi.

Host'da ishga tushirishda `DATABASE_URL` va `REDIS_URL` ni host'dan yetib bo'ladigan xizmatlarga yo'naltiring;
Compose default DNS nomlari (`postgres`, `redis`) host muhitida ishlamaydi.

```bash
uv run alembic revision --autogenerate -m "add orders"  # diff'ni tekshirib commit qiling
uv run alembic upgrade head
uv run python -m bot serve
uv run python -m bot worker
```

## Kuzatuv va operatsiyalar

Grafana dashboard: service up, inbox pending/failed, HTTP responses, latency p95, update tezligi,
eng eski pending update yoshi. Prometheus alert qoidalari: xizmat ishlamayapti, navbat kechikyapti,
dead-letter bor yoki HTTP 5xx ko'paygan. Alertlar UI'da ko'rinadi; Slack/email uchun Alertmanager
receiver'i alohida ulanadi. Metrics endpoint Bearer `METRICS_TOKEN` bilan himoyalangan.
User ID va xabar matni metrics label'lariga yozilmaydi. Loglarda request/update ID va exception turi bor;
payload, exception string va tokenlar yozilmaydi. Sentry optional: `SENTRY_DSN`; PII o'chirilgan.

```bash
make logs
make backup
docker compose run --rm app python -m bot retry-update --update-id 12345
docker compose run --rm app python -m bot cleanup-inbox
```

Successful payload darhol `{}` ga almashtiriladi; dedup ID default 7 kun qoladi. Cleanup'ni kuniga bir
marta cron/scheduler bilan rejalashtiring. Failed payload operator tekshiruvigacha saqlanadi: unga
DB access va retention siyosatini qo'llang. Cleanup eski dedup ID'larni ham yo'qotadi; retention'dan
eski update qayta yuborilsa yana ishlanishi mumkin. Retry buyrug'i faqat `failed` update uchun ishlaydi.

Production HTTPS, tokenlar, backup/restore: [deployment](docs/deployment.md).
Queue va tranzaksiyalar: [architecture](docs/architecture.md).

Rasmiy manbalar: [aiogram webhook](https://docs.aiogram.dev/en/latest/dispatcher/webhook.html),
[Telegram setWebhook](https://core.telegram.org/bots/api#setwebhook),
[SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html),
[Redis FSM](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/storages.html).
