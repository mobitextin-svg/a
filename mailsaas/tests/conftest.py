"""Shared pytest fixtures for the MailSaaS test suite.

Each test gets a fresh, throwaway SQLite database (seeded with the default
admin) and a Flask test client. CSRF and rate-limiting are disabled under
TESTING, so tests can POST forms directly.
"""
import os
import tempfile

# Point the import-time `app = create_app()` at a throwaway DB so simply
# importing the package never touches the real mailsaas.sqlite3.
os.environ.setdefault("MAILSAAS_DB",
                      os.path.join(tempfile.mkdtemp(), "import.sqlite3"))
os.environ.setdefault("MAILSAAS_SECRET", "test-secret")

import pytest  # noqa: E402

from mailsaas.app import (create_app, DEFAULT_ADMIN_EMAIL,  # noqa: E402
                          DEFAULT_ADMIN_PASSWORD)


@pytest.fixture
def app(tmp_path, monkeypatch):
    """A fresh application backed by an isolated database file."""
    monkeypatch.setenv("MAILSAAS_DB", str(tmp_path / "test.sqlite3"))
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    """An anonymous test client (not logged in)."""
    return app.test_client()


@pytest.fixture
def auth(app):
    """A test client already signed in as the default admin."""
    c = app.test_client()
    r = c.post("/login", data={"email": DEFAULT_ADMIN_EMAIL,
                               "password": DEFAULT_ADMIN_PASSWORD})
    assert r.status_code in (200, 302)
    return c


def csv_rows(prefix, start, end):
    """Build a header + 'email,name' CSV body for a range of fake contacts."""
    body = "Email,Name\n"
    body += "\n".join(f"{prefix}{i}@example.com,User {i}"
                      for i in range(start, end))
    return body
