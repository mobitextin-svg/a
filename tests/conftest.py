"""Shared pytest fixtures: an isolated app + DB per test, with role clients."""
import os
import sqlite3
import tempfile

import pytest

# Ensure the very first import of the app uses a throwaway DB and no real SMTP.
os.environ.setdefault("MAILSAAS_DB", os.path.join(tempfile.gettempdir(),
                                                  "mailsaas-test-boot.sqlite3"))
os.environ.pop("MAILSAAS_SMTP_HOST", None)


@pytest.fixture
def app(tmp_path):
    os.environ["MAILSAAS_DB"] = str(tmp_path / "test.sqlite3")
    os.environ.pop("MAILSAAS_SMTP_HOST", None)
    from mailsaas.app import create_app
    application = create_app()
    application.testing = True
    return application


@pytest.fixture
def db_path():
    return os.environ["MAILSAAS_DB"]


@pytest.fixture
def query(db_path):
    def _q(sql, *args):
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, args).fetchall()
        con.close()
        return rows
    return _q


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(app):
    """First account on the platform == super-admin."""
    c = app.test_client()
    c.post("/signup", data={"name": "Root", "email": "root@hq.com",
                            "password": "secret1"}, follow_redirects=True)
    return c


@pytest.fixture
def user(app, admin):
    """A regular user created by the admin (own isolated workspace)."""
    admin.post("/admin", data={"action": "create_user", "name": "Joe",
                               "email": "joe@co.com", "password": "joepass1",
                               "plan": "Pro", "role": "User", "status": "active"},
               follow_redirects=True)
    c = app.test_client()
    c.post("/login", data={"email": "joe@co.com", "password": "joepass1"},
           follow_redirects=True)
    return c
