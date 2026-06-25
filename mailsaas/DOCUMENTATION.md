# MailSaaS — User & Operator Documentation

A complete guide to using and running the platform. For the production
architecture see **[PRODUCTION.md](PRODUCTION.md)**; for a feature overview see
**[README.md](README.md)**.

---

## Getting started

1. **Sign up** at `/signup` — you get an isolated workspace seeded with demo data.
2. **Verify your email** via the link in the welcome banner (tokenised).
3. Follow the **Get started checklist** on the dashboard — it tracks real
   progress (email verified, 2FA on, API key created, first verifications,
   teammate invited, plan upgraded).

> The **first account created** on a fresh install becomes the **Super Admin**
> and gains the 🛡️ Admin Panel.

---

## Modules

### Email Verification
Single and bulk verification with an explainable, layered engine:
syntax → MX → SMTP → catch-all/accept-all → disposable → role → greylisting →
mailbox-full → spam-trap → domain age. Returns a **deliverability score
(0–100)**, an independent **risk score**, and per-check results. Export history
to CSV. Also available via the JSON API.

### Bulk Email / Campaigns
Compose with merge tags (`{{name}}`), save drafts, then move a campaign through
**Draft → Scheduled → Running → Completed**, with **Pause/Resume**. Templates,
A/B subjects, personalization and a live delivery queue are included.

### Contacts
Lists, tags, status tabs (active/suppressed/unsubscribed/bounced),
**search + pagination** (25/page, indexed for large lists), CSV import/export,
**duplicate removal**, and **GDPR erasure** (hard-delete + permanent
suppression).

### AI Center
Email writer, subject generator, A/B subjects, spam score, rewrite, CTA
generator, translate, personalization, tone analyzer, reply-intent detection,
send-time prediction. Runs on a built-in generator offline; plug in a real LLM
by implementing `ai._llm_complete()` and setting `ai.USE_LLM = True`.

### Deliverability / SMTP / Domains / Warm-up
Inbox-placement and provider scores, blacklist monitor, spam test; SMTP relays
with live health (IP score, DNS/PTR/SPF/DKIM/DMARC/TLS/RBL, latency, inbox %);
SMTP **pools** (round-robin/weighted/failover); domain authentication
(SPF/DKIM/DMARC) with DNS verification; 14-day IP **warm-up** plans.

### Queue Manager & Monitoring
Live queue states (pending/processing/delivered/retry/failed/dead) with
**speed, remaining, ETA**. Monitoring shows **real CPU/RAM/Disk**, DB and Redis
status, queue depth and a service board.

### Reports
Aggregate and per-campaign delivery/open/click/bounce, plus geo and device
breakdowns with inline charts.

---

## API

Authenticate with a Bearer token (create one under **API → API Keys**; rotate or
revoke anytime).

```bash
curl "https://YOUR_HOST/api/v1/verify?email=test@gmail.com" \
     -H "Authorization: Bearer ms_live_xxx"
```

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/v1/verify?email=` | Verify one address. **60 req/min per key.** |
| GET | `/api/v1/health` | Service health |

Responses are JSON with `result`, `score`, `risk_score`, `reason` and a
per-check `checks` object. Rate-limited requests return **429** with
`retry_after`.

### Webhooks
Register endpoints under **Webhooks** and subscribe to events
(Delivered/Opened/Clicked/Bounce/Spam/Unsubscribe). Each delivery is signed
(`X-MailSaaS-Signature`). Use **Test** to fire a sample event.

---

## Security

| Control | Detail |
|---|---|
| Passwords | bcrypt hashing |
| 2FA | Real RFC-6238 TOTP (Google Authenticator/Authy/1Password) |
| Email verification | Tokenised on signup |
| Password reset | `/forgot` → `/reset/<token>`, 1-hour expiry |
| Sessions | Sliding 30-min timeout, HttpOnly/SameSite cookies, "sign out everywhere" |
| CSRF | Token enforced on all state-changing forms |
| Rate limiting | Login 10/min per IP · API 60/min per key |
| API keys | Rotation & revocation |
| Audit | Activity log + login history (IP/device/result) |

Tune the session timeout with `MAILSAAS_SESSION_MINUTES` (default 30).

---

## Roles & administration

| Role | Capabilities |
|---|---|
| **Super Admin** | Create admins, manage all users, plans, billing, SMTP, white-label |
| **Admin** | Create/edit users, assign plans, suspend, view reports |
| **Manager** | Team, campaigns, contacts |
| **User** | Send/verify, campaigns, reports, billing |

**Admin Panel** (`/admin`, admin workspaces only): create users
(name/email/password/plan/role/status → isolated workspace), suspend/activate,
change plan/role inline, and promote to Admin (super-admin only). Suspending a
user blocks login and revokes their sessions.

---

## Configuration (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `MAILSAAS_SECRET` | Session signing key | random per boot |
| `MAILSAAS_DB` | SQLite file path | `mailsaas/mailsaas.sqlite3` |
| `DATABASE_URL` | Postgres DSN (prod) | — |
| `REDIS_URL` | Celery broker / cache | `redis://localhost:6379/0` |
| `MAILSAAS_SESSION_MINUTES` | Session timeout | `30` |
| `PORT` | Dev server port | `5005` |

---

## Performance notes

- Tenant-scoped tables are **indexed on `account_id`** (and `account_id,email`)
  for fast lookups as lists grow.
- Contacts are **paginated** server-side (25/page) with indexed search.
- Bulk sends/verification should run via `tasks.enqueue(...)` so the web tier
  stays responsive; it runs inline in dev and dispatches to Celery in prod.
- For very large tenants, migrate to PostgreSQL (see PRODUCTION.md) — the
  storage layer is isolated in `db.py`.
