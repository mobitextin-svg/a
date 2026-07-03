# 📨 MailSaaS — Enterprise Email Verification & Delivery Platform

[![CI](https://github.com/mobitextin-svg/a/actions/workflows/ci.yml/badge.svg)](https://github.com/mobitextin-svg/a/actions/workflows/ci.yml)

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

**Standard fields:** Email (required), Name, Mobile, Company, City, State.
**Automatic header mapping** converts any upload to the standard format — columns
like *Email Address, Full Name, Phone, Company Name, District, Province* are
recognised automatically (no manual mapping). The import pipeline auto-detects
headers, removes blank rows, trims spaces, validates emails, normalises mobile
numbers, removes duplicate emails and skips invalid records.

**Statuses:** Active · Blocked · Unsubscribed · Bounced (blocked & bounced/unsub
are excluded from every campaign).

**Duplicate handling** defaults to **Remove Duplicates** (one record per email);
advanced options are **Skip Duplicates** and **Update Existing Contacts**. There is
deliberately no "Keep Both" — a professional list never stores an email twice.
Each import ends with a full summary:

```
✅ Import Completed Successfully
File Name          : customers.xlsx
Total Records      : 400
Imported           : 200
Updated            : 0
Duplicates Removed  : 200
Invalid Emails     : 8
Blank Rows         : 3
Final Contacts     : 1,200
[View Contacts] [Download Error Report] [Undo Import]
```

### Campaign wizard (7 steps)
**Campaign Details → Recipients → Email Template → Attachments 📎 → Sender &
Domain → Inbox Analysis → Review/Send.** The Attachments step supports drag &
drop and multi-file upload with live progress, per-file size display and a
running total. Limits: **10 MB/file · 25 MB total · 10 files** (safe Gmail/Outlook
ceiling). Allowed: PDF, Word, Excel, PowerPoint, TXT, CSV, ZIP and images —
executables (.exe/.bat/.msi/.js) are rejected so providers don't flag the mail.
Attachments are carried through to the actual SMTP send as a multipart/mixed
message.

### Tests
```bash
pip install -r requirements-dev.txt
python -m pytest mailsaas/tests -q     # from the repo root
```
The suite (`mailsaas/tests/`) covers auth & the default admin, the contacts
import pipeline (header mapping, the 1,000+500→1,300 de-dupe, statuses, tags,
favourites), campaign attachments (validation, limits, multipart assembly),
logo/header auto-resize, the campaign wizard flow (incl. Save as Ready) and a
render smoke-test of every major page.

It runs automatically on every push and pull request via **GitHub Actions**
(`.github/workflows/ci.yml`) on Python 3.10 / 3.11 / 3.12.

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
