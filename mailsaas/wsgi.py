"""WSGI entrypoint for production servers (Gunicorn / uWSGI).

    gunicorn -w 4 -b 0.0.0.0:8000 mailsaas.wsgi:app
"""
from mailsaas.app import app  # noqa: F401
