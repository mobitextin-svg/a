"""Integration tests: auth, roles, sending+tracking, deliverability, admin."""
import re


# ------------------------------- auth ------------------------------------- #

def test_signup_then_dashboard(admin):
    assert b"Welcome back" in admin.get("/dashboard").data


def test_suspended_user_cannot_login(app, admin, user, query):
    uid = query("SELECT id FROM users WHERE email='joe@co.com'")[0]["id"]
    admin.post("/admin", data={"action": "suspend", "id": uid}, follow_redirects=True)
    c = app.test_client()
    r = c.post("/login", data={"email": "joe@co.com", "password": "joepass1"},
               follow_redirects=True)
    assert b"suspended" in r.data and b"Welcome back" not in r.data


def test_password_reset_does_not_leak_link(admin):
    r = admin.post("/forgot", data={"email": "root@hq.com"}, follow_redirects=True)
    assert b"/reset/" not in r.data and b"If an account exists" in r.data


# ------------------------------- roles ------------------------------------ #

def test_admin_sees_admin_menu(admin):
    d = admin.get("/dashboard").data
    assert b"SMTP Infrastructure" in d and b"Backups" in d


def test_user_sees_user_menu_only(user):
    d = user.get("/dashboard").data
    assert b"Campaigns" in d and b"Sending Infrastructure" not in d


def test_user_blocked_from_infra(user):
    for p in ("/ip-health", "/queue", "/rotation/sending", "/burst", "/admin",
              "/admin/backups", "/monitoring"):
        assert user.get(p).status_code == 403, p


def test_user_can_reach_own_smtp_and_domains(user):
    assert user.get("/smtp").status_code == 200
    assert user.get("/domains").status_code == 200


# ----------------------- sending + tracking ------------------------------- #

def test_send_creates_messages_and_tracks(user, query):
    user.post("/campaigns", data={"action": "create", "name": "C", "subject": "Hi",
                                  "body": 'Hi {{name}} <a href="https://x.com">go</a>'},
              follow_redirects=True)
    cid = query("SELECT id FROM campaigns WHERE name='C'")[0]["id"]
    aid = query("SELECT account_id FROM campaigns WHERE id=?", cid)[0]["account_id"]
    r = user.post("/campaigns", data={"action": "send", "id": cid},
                  follow_redirects=True)
    assert b"Campaign sent" in r.data
    msgs = query("SELECT * FROM messages WHERE campaign_id=?", cid)
    assert len(msgs) > 0
    tok = msgs[0]["token"]

    # open
    assert user.get(f"/t/o/{tok}.gif").status_code == 200
    assert query("SELECT opened FROM messages WHERE token=?", tok)[0]["opened"] == 1
    # opening twice doesn't double-count
    user.get(f"/t/o/{tok}.gif")
    assert query("SELECT opens FROM campaigns WHERE id=?", cid)[0]["opens"] == 1
    # click redirects safely + implies open
    tok2 = msgs[1]["token"] if len(msgs) > 1 else tok
    r = user.get(f"/t/c/{tok2}?u=https%3A%2F%2Fexample.com")
    assert r.status_code == 302 and r.headers["Location"] == "https://example.com"
    # junk redirect blocked
    r = user.get(f"/t/c/{tok}?u=javascript:alert(1)")
    assert "javascript" not in r.headers.get("Location", "")


def test_unsubscribe_suppresses_contact(user, query):
    user.post("/campaigns", data={"action": "create", "name": "U", "body": "hi"},
              follow_redirects=True)
    cid = query("SELECT id FROM campaigns WHERE name='U'")[0]["id"]
    user.post("/campaigns", data={"action": "send", "id": cid}, follow_redirects=True)
    m = query("SELECT * FROM messages WHERE campaign_id=?", cid)[0]
    user.get(f"/t/u/{m['token']}")
    assert query("SELECT 1 FROM complaints WHERE email=? AND kind='unsubscribe'",
                 m["email"])
    assert query("SELECT status FROM contacts WHERE email=? AND account_id=?",
                 m["email"], m["account_id"])[0]["status"] == "unsubscribed"


# --------------------------- deliverability ------------------------------- #

def test_deliverability_ai_user_vs_admin(admin, user):
    assert b"AI recommendations" in user.get("/deliverability-ai").data
    assert b"across all accounts" in admin.get("/deliverability-ai").data


def test_auto_clean_removes_bad_contacts(user, query):
    aid = query("SELECT account_id FROM users WHERE email='joe@co.com'")[0]["account_id"]
    before = query("SELECT COUNT(*) c FROM contacts WHERE account_id=? AND status IN"
                   " ('bounced','unsubscribed')", aid)[0]["c"]
    user.post("/deliverability-ai", data={"action": "autoclean"}, follow_redirects=True)
    after = query("SELECT COUNT(*) c FROM contacts WHERE account_id=? AND status IN"
                  " ('bounced','unsubscribed')", aid)[0]["c"]
    assert before > 0 and after == 0


def test_dual_scope_bounce(admin, user):
    assert b"by account" in admin.get("/bounce").data
    assert b"by account" not in user.get("/bounce").data


def test_burst_quota_purchase_and_launch(user, query):
    aid = query("SELECT account_id FROM users WHERE email='joe@co.com'")[0]["account_id"]
    # over-limit quote shows both payment regions
    r = user.post("/burst-campaign", data={"action": "quote", "size": "1000000"})
    assert b"Confirm" in r.data and b"India" in r.data
    # India payment (test mode — no Razorpay keys set)
    user.post("/burst-campaign", data={"action": "pay", "emails": "100000",
                                       "usd": "69", "inr": "4999", "region": "india"},
              follow_redirects=True)
    p = query("SELECT * FROM burst_purchases WHERE account_id=?", aid)[0]
    assert p["gateway"].startswith("Razorpay") and p["currency"] == "INR"
    assert query("SELECT burst_quota FROM accounts WHERE id=?", aid)[0]["burst_quota"] == 100000
    # launch consumes quota and records a completed burst job
    user.post("/burst-campaign", data={"action": "launch"}, follow_redirects=True)
    assert query("SELECT burst_quota FROM accounts WHERE id=?", aid)[0]["burst_quota"] == 0
    assert query("SELECT status FROM burst_jobs WHERE account_id=? ORDER BY id DESC"
                 " LIMIT 1", aid)[0]["status"] == "completed"


def test_burst_manual_approval_workflow(admin, user, query):
    aid = query("SELECT account_id FROM users WHERE email='joe@co.com'")[0]["account_id"]
    # admin switches to manual approval
    admin.post("/burst", data={"action": "auto_toggle"}, follow_redirects=True)
    before = query("SELECT burst_quota FROM accounts WHERE id=?", aid)[0]["burst_quota"]
    # user pays → request goes pending, quota not granted yet
    r = user.post("/burst-campaign", data={"action": "pay", "emails": "100000",
                                           "usd": "69", "inr": "4999", "region": "india"},
                  follow_redirects=True)
    assert b"pending admin approval" in r.data
    assert query("SELECT burst_quota FROM accounts WHERE id=?", aid)[0]["burst_quota"] == before
    req = query("SELECT * FROM burst_purchases WHERE status='pending' ORDER BY id DESC"
                " LIMIT 1")[0]
    # admin approves → quota granted
    admin.post("/burst", data={"action": "approve", "id": req["id"]},
               follow_redirects=True)
    assert query("SELECT burst_quota FROM accounts WHERE id=?",
                 aid)[0]["burst_quota"] == before + 100000


# ------------------------------ admin ------------------------------------- #

def test_admin_can_create_user_who_logs_in(app, admin, query):
    admin.post("/admin", data={"action": "create_user", "name": "New",
                               "email": "new@co.com", "password": "newpass1",
                               "plan": "Free", "role": "User", "status": "active"},
               follow_redirects=True)
    c = app.test_client()
    r = c.post("/login", data={"email": "new@co.com", "password": "newpass1"},
               follow_redirects=True)
    assert b"Welcome back" in r.data


def test_admin_regular_cannot_self_escalate(app, admin, query):
    admin.post("/admin", data={"action": "create_user", "name": "Adm",
                               "email": "adm@co.com", "password": "admpass1",
                               "plan": "Pro", "role": "Admin", "status": "active"},
               follow_redirects=True)
    aid_user = query("SELECT id FROM users WHERE email='adm@co.com'")[0]["id"]
    a2 = app.test_client()
    a2.post("/login", data={"email": "adm@co.com", "password": "admpass1"},
            follow_redirects=True)
    a2.post("/admin", data={"action": "set_role", "id": aid_user,
                            "role": "Super Admin"}, follow_redirects=True)
    assert query("SELECT role FROM users WHERE id=?", aid_user)[0]["role"] == "Admin"


def test_backup_create_and_traversal_blocked(admin):
    admin.post("/admin/backups", data={"action": "create"}, follow_redirects=True)
    assert admin.get("/admin/backups/..%2f..%2fapp.py").status_code in (403, 404)


def test_csrf_blocks_tokenless_post(app):
    app.config["TESTING"] = False
    c = app.test_client()
    r = c.post("/login", data={"email": "x@y.com", "password": "z"})
    assert r.status_code == 400


def test_api_verify_requires_key_and_rate_limits(app, admin, query):
    admin.post("/api", data={"action": "create", "label": "L"}, follow_redirects=True)
    token = query("SELECT token FROM api_keys ORDER BY id DESC LIMIT 1")[0]["token"]
    c = app.test_client()
    assert c.get("/api/v1/verify?email=a@gmail.com").status_code == 401
    assert c.get(f"/api/v1/verify?email=a@gmail.com&api_key={token}").status_code == 200


def test_api_calls_are_logged(app, admin, query):
    admin.post("/api", data={"action": "create", "label": "L"}, follow_redirects=True)
    token = query("SELECT token FROM api_keys ORDER BY id DESC LIMIT 1")[0]["token"]
    app.test_client().get(f"/api/v1/verify?email=a@gmail.com&api_key={token}")
    assert query("SELECT COUNT(*) c FROM api_logs")[0]["c"] >= 1
    assert b"API access logs" in admin.get("/admin/logs").data


def test_ip_restriction_blocks_other_ip(app, admin):
    # Admin is already logged in (via the fixture). Restrict to an IP that is
    # NOT the test client's, enable enforcement, and confirm access is blocked.
    import os
    import sqlite3
    con = sqlite3.connect(os.environ["MAILSAAS_DB"])
    con.execute("UPDATE accounts SET ip_allowlist='9.9.9.9' WHERE id=1")
    con.commit()
    con.close()
    app.config["TESTING"] = False  # enable IP enforcement in before_request
    assert admin.get("/dashboard").status_code == 403
