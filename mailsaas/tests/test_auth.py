"""Authentication: the permanent default admin and basic login flow."""
from mailsaas.app import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD


def test_default_admin_can_log_in(client):
    r = client.post("/login", data={"email": DEFAULT_ADMIN_EMAIL,
                                    "password": DEFAULT_ADMIN_PASSWORD})
    assert r.status_code == 302
    assert "/dashboard" in r.headers["Location"]


def test_wrong_password_is_rejected(client):
    r = client.post("/login", data={"email": DEFAULT_ADMIN_EMAIL,
                                    "password": "wrong"})
    assert r.status_code == 200          # re-renders the login page
    assert b"Invalid email or password" in r.data


def test_dashboard_requires_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_logout(auth):
    assert auth.get("/dashboard").status_code == 200
    auth.get("/logout")
    assert auth.get("/dashboard").status_code == 302


def test_admin_is_seeded_once(app):
    from mailsaas import db as D
    with app.app_context():
        n = D.query("SELECT COUNT(*) c FROM users WHERE email=?",
                    (DEFAULT_ADMIN_EMAIL,), one=True)["c"]
    assert n == 1
