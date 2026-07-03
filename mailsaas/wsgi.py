"""WSGI entry point for production servers (e.g. gunicorn mailsaas.wsgi:app)."""
from mailsaas.app import app  # noqa: F401  (imported for the WSGI server)

if __name__ == "__main__":
    app.run()
