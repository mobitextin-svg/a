"""
Background worker scaffold (Celery + Redis).

In development the Flask app runs everything in-process. For production, bulk
sending and bulk verification should run **out of band** so the web tier stays
responsive:

    Flask  →  Redis (broker)  →  Celery workers  →  SMTP / verification

This module defines that worker layer. It degrades gracefully: if Celery isn't
installed (e.g. the dev sandbox), `enqueue()` runs the job synchronously so the
same code path works everywhere. Wire it up in production with:

    REDIS_URL=redis://redis:6379/0 celery -A mailsaas.tasks.celery worker -l info
"""
import os

BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    from celery import Celery  # type: ignore
    celery = Celery("mailsaas", broker=BROKER_URL, backend=BROKER_URL)
    celery.conf.update(task_acks_late=True, worker_prefetch_multiplier=1,
                       task_default_queue="mailsaas")
    HAVE_CELERY = True
except Exception:  # pragma: no cover - sandbox without celery
    celery = None
    HAVE_CELERY = False


def _task(fn):
    """Register `fn` as a Celery task when available, else leave it callable."""
    if HAVE_CELERY:
        return celery.task(name=f"mailsaas.{fn.__name__}")(fn)
    return fn


@_task
def send_campaign(campaign_id, account_id):
    """Send a campaign in the background.

    Production implementation would: load recipients, render per-recipient
    content, pick an SMTP relay from the pool (round-robin / weighted /
    failover), respect warm-up + rate limits, stream events to webhooks, and
    record opens/clicks via tracking pixels & wrapped links.
    """
    # Placeholder: real send loop goes here.
    return {"campaign_id": campaign_id, "account_id": account_id, "status": "queued"}


@_task
def verify_bulk_async(account_id, emails):
    """Verify a large list off the request path and persist results."""
    from .verify import verify_email
    return [verify_email(e) for e in emails]


@_task
def process_bounce(event):
    """Classify an inbound bounce/complaint and update suppression lists."""
    return {"processed": True, "event": event}


def enqueue(task, *args, **kwargs):
    """Submit a task to the broker, or run it inline when Celery is absent."""
    if HAVE_CELERY:
        return task.delay(*args, **kwargs)
    return task(*args, **kwargs)
