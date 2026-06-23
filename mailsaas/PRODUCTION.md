# Production Deployment Guide

MailSaaS runs out of the box on **Flask + SQLite** for development. For
production scale (thousands of concurrent users, millions of emails), use the
topology below. The scaffolding for all of it ships in this repo.

```
            ┌─────────┐
  Internet →│  NGINX  │  TLS, static files, reverse proxy
            └────┬────┘
                 │
            ┌────▼────────┐
            │  Gunicorn   │  4+ Flask workers  (mailsaas.wsgi:app)
            └────┬────────┘
                 │ enqueue()
            ┌────▼────┐        ┌──────────────┐
            │  Redis  │───────▶│   Celery     │  send / verify / bounce workers
            └─────────┘        └──────┬───────┘
                                      │
                              ┌───────▼────────┐     ┌──────────────┐
                              │  PostgreSQL    │     │ SMTP / ESPs  │
                              └────────────────┘     └──────────────┘
```

## 1. One command (local prod-like stack)

```bash
docker compose up --build
# NGINX on http://localhost  →  Gunicorn  →  Redis + Celery + Postgres
```

Files involved: `Dockerfile`, `docker-compose.yml`, `deploy/nginx.conf`,
`mailsaas/wsgi.py`, `mailsaas/tasks.py`.

## 2. SQLite → PostgreSQL

The storage layer is isolated in `mailsaas/db.py`, so the swap is contained:

1. Add `psycopg[binary]` and `SQLAlchemy` (or `psycopg` + raw SQL) to
   `requirements.txt`.
2. Read `DATABASE_URL` (already passed by `docker-compose.yml`) and branch:
   - `sqlite://…` → current `sqlite3` path (dev)
   - `postgresql://…` → psycopg connection pool (prod)
3. Port the schema in `db.SCHEMA` — it is standard SQL; the only changes are
   `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL/BIGSERIAL PRIMARY KEY` and
   `TEXT` timestamps → `TIMESTAMPTZ`.
4. Use a connection pool (PgBouncer or `psycopg_pool`) sized to your worker
   count.

Because every table already carries `account_id`, the multi-tenant isolation
model is unchanged — optionally enforce it at the DB layer with Postgres
**Row-Level Security** policies keyed on a `SET app.account_id`.

## 3. Background workers (Celery)

`mailsaas/tasks.py` already defines the worker app and tasks
(`send_campaign`, `verify_bulk_async`, `process_bounce`). Call sites use
`enqueue(task, …)`, which runs inline in dev and dispatches to Redis in prod.

```bash
REDIS_URL=redis://redis:6379/0 \
  celery -A mailsaas.tasks.celery worker -l info -Q mailsaas
```

Move bulk verification and campaign sends behind `enqueue()` so the request
returns immediately and the workers do the heavy lifting (rate-limited per
SMTP relay, respecting warm-up curves).

## 4. Configuration (env vars)

| Variable | Purpose | Default |
|---|---|---|
| `MAILSAAS_SECRET` | Flask session signing key | random per boot |
| `DATABASE_URL` | Postgres DSN in prod | SQLite file |
| `REDIS_URL` | Celery broker / cache | `redis://localhost:6379/0` |
| `MAILSAAS_SESSION_MINUTES` | Sliding session timeout | `30` |
| `PORT` | Dev server port | `5005` |

## 5. Security checklist (status in this build)

- ✅ CSRF protection on all state-changing forms (`register_security`)
- ✅ Sliding session timeout + HttpOnly / SameSite cookies
- ✅ API key rotation & revocation
- ✅ bcrypt password hashing
- ✅ Login history + audit logs
- ✅ 2FA toggle (wire to TOTP/`pyotp` for full enforcement)
- ☐ TLS termination (NGINX — add your certs)
- ☐ Rate limiting (add `flask-limiter`, already a pattern in the sibling app)
- ☐ SSO / SAML (enterprise add-on)

## 6. Scaling notes

- Run Gunicorn with `workers = 2 × CPU + 1`; keep workers stateless.
- Scale Celery workers horizontally; shard queues per concern
  (`send`, `verify`, `bounce`) for isolation.
- Put PgBouncer in front of Postgres; use read replicas for analytics.
- Cache hot dashboard aggregates in Redis with short TTLs.
- For millions of sends, a FastAPI ingestion API in front of the same Redis
  queue is a drop-in upgrade for the web tier without touching the workers.
