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
    assert b"Sending Infrastructure" in d and b"Backups" in d


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
