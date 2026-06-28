# 📨 MailSaaS — Enterprise Email Verification & Delivery Platform

A self-contained, enterprise-grade SaaS platform for **email verification** and
**bulk email delivery**, built with Flask + SQLite (matches the repo's
`fileshare` style — single process, server-rendered, no build step).

The entire product information architecture from the brief is navigable, with a
fully **functional verification engine** and working CRUD across the core
modules.

> **Production?** See **[PRODUCTION.md](PRODUCTION.md)** for the NGINX → Gunicorn
> → Redis → Celery → PostgreSQL topology — scaffolding ships in this repo
> (`Dockerfile`, `docker-compose.yml`, `deploy/nginx.conf`, `wsgi.py`,
> `tasks.py`). Run it with `docker compose up --build`.

📖 Full usage guide: **[DOCUMENTATION.md](DOCUMENTATION.md)**

### Performance & UX
- Server-side **pagination + indexed search** for large contact lists (25/page)
- DB indexes on every tenant-scoped table · guided **onboarding checklist** on the dashboard
- **Rate limiting**: login 10/min per IP · API 60/min per key (HTTP 429)

### Payments (Burst packs — India)
Razorpay test checkout (UPI · UPI-QR · cards · net banking) goes live when you
set test-mode keys; otherwise it runs in a safe test/simulated mode.
```
RAZORPAY_KEY_ID=rzp_test_xxxx   RAZORPAY_KEY_SECRET=xxxx
UPI_VPA=you@okhdfcbank  UPI_NAME="Your Business"
BANK_NAME=... BANK_ACC=... BANK_IFSC=...     # for the bank-transfer option
```

### Security & Authentication
- **Email verification** on signup · **password reset** (tokenised, 1h expiry)
- **Real TOTP 2FA** (RFC 6238, stdlib-only — works with Google Authenticator/Authy/1Password)
- **Session management**: sliding 30-min timeout, HttpOnly/SameSite cookies, "sign out everywhere"
- CSRF protection on every form · API-key rotation & revocation · bcrypt hashing · login history · audit logs

### UI
- Dark / light theme toggle · toast notifications · animated counters
- Live SVG charts · progress bars · mobile-responsive hamburger navigation

---

## Quick start

**One-click (easiest):**
- **Windows** — double-click **`start.bat`**
- **macOS / Linux** — run **`./start.sh`** (or `bash start.sh`)

These auto-install dependencies, launch the server, and open your browser.

**Manual:**
```bash
cd mailsaas
pip install -r requirements.txt
python run.py
# → http://127.0.0.1:5005
```

Use a different port with the `PORT` env var, e.g. `PORT=5060 python run.py`.

### Default admin login
A permanent administrator is seeded automatically on first run so the platform
is always reachable:

| Email | Password |
| --- | --- |
| `admin@gmail.com` | `admin1234` |

Change it afterwards from **Settings → Security**. Override the seed for
production with `MAILSAAS_ADMIN_EMAIL` / `MAILSAAS_ADMIN_PASSWORD`.

### Contacts
A single **👥 Contacts** menu opens one list-first dashboard — no separate
Import/Export/Settings pages. Pick a list (or **All Contacts** / **Suppression**)
from the left rail and act on it from the toolbar:

- **Lists** — create, rename, duplicate, **merge**, move, copy, delete
- **Contacts** — view, search, filter, edit, delete, move/assign, bulk actions
- **Import** — CSV, Excel (.xlsx) or copy & paste, **de-duplicated by email**
- **Export** — CSV or Excel (whole account or one list)
- **📊 Statistics** — total, active, bounced, unsubscribed per list
- **🚫 Suppression** — unsubscribed, bounced, complaints, blocked emails (account-wide)
- **⚙ Settings** — duplicate check, default import rule, custom fields (gear modal)

Imports skip addresses that already exist (matched by email, or email+name if you
choose), so the same person never receives two copies of a campaign. Each import
ends with a summary:

```
✅ Import Completed
Records in File      : 500
New Contacts Added   : 300
Duplicate Contacts   : 200 (Skipped)
Final Contact Count  : 1300
```

### Tests
```bash
pip install -r requirements-dev.txt
python -m pytest mailsaas/tests -q     # from the repo root
```
The suite (`mailsaas/tests/`) covers the engines (verification, rotation,
deliverability AI, TOTP, rendering) and the app (auth, 2FA, role split + access
gating, real send + open/click/unsubscribe tracking, deliverability, admin,
CSRF, API rate-limit).

Create an account on the signup screen — your workspace is auto-seeded with
realistic demo data (contacts, campaigns, SMTP relays, domains, invoices) so
every screen has something to show.

> `dnspython` is optional. With it installed (and outbound DNS available) the
> verifier performs **real MX lookups**; otherwise it falls back to
> deterministic heuristics so results are always explainable.

---

## What's functional

| Module | Status | What works |
|---|---|---|
| **Auth** | ✅ Full | Signup, login, logout, bcrypt hashing, sessions, per-tenant workspaces |
| **Dashboard** | ✅ Full | Live stats, delivery rates, recent activity, latest campaigns |
| **Email Verification** | ✅ Full | Syntax, MX, disposable, role, free-provider, typo-suggestion, catch-all heuristic, deliverability score (0–100); single + bulk + CSV export + history |
| **Contacts** | ✅ Full | Add, CSV import, suppress, delete, status tabs, export |
| **Campaigns / Sender** | ✅ Full | Create draft, clone, advance through Draft→Scheduled→Running→Completed, delivery queue |
| **SMTP Servers** | ✅ Full | Add relays, dedicated IP, health, warm-up, per-server limit meters |
| **Domains** | ✅ Full | Add domain, SPF/DKIM/DMARC status, DNS verify, reputation |
| **Reports** | ✅ Full | Aggregate + per-campaign metrics, geo & device breakdowns |
| **API** | ✅ Full | Create/revoke keys, live `GET /api/v1/verify` (Bearer auth), docs |
| **Billing** | ✅ Full | Plan switching, credit top-ups, invoices |
| **Team** | ✅ Full | Invite members, roles, activity log |
| **Settings** | ✅ Full | Profile, password change, 2FA toggle, branding, audit log |
| **Enterprise Modules** | ✅ Page | Pools, IP rotation, deliverability AI, multi-region, white-label — health dashboard |
| Integrations / Automation / Notifications / Support | 🧩 Scaffold | Consistent, navigable landing pages generated from the sitemap |

Multi-tenant by design: nearly every table carries an `account_id`, so a single
deployment serves many isolated tenants.

---

## JSON API

```bash
curl "http://127.0.0.1:5005/api/v1/verify?email=test@gmail.com" \
     -H "Authorization: Bearer YOUR_API_KEY"
```

```json
{ "email": "test@gmail.com", "result": "valid", "score": 100,
  "reason": "Deliverable", "checks": { "syntax": true, "mx": true, ... } }
```

---

## Layout

```
mailsaas/
├── app.py          # app factory, auth, all module routes, JSON API
├── db.py           # SQLite schema, helpers, demo-data seeding
├── verify.py       # email verification engine (syntax/MX/disposable/role/...)
├── nav.py          # the full product sitemap — drives sidebar + scaffold pages
├── run.py          # `python run.py` launcher
├── requirements.txt
├── templates/      # Jinja templates (base + one per module)
└── static/style.css
```

## Architecture notes

- **Single source of truth for the sitemap** (`nav.py`): the sidebar and the
  auto-generated landing pages both render from it, so the IA never drifts.
- **Stateless verification engine** (`verify.py`) is import-safe and unit-testable
  in isolation, with a graceful no-network fallback.
- **Bespoke views** for built modules; a single generic `module.html` covers the
  rest, keeping the whole platform browsable without 100 hand-written pages.
