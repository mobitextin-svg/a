"""
Bulk lookup engine.

Takes a list of raw number strings, normalises + de-duplicates them, then runs
lookups concurrently against the active provider with a simple rate limiter.
Progress is tracked live so a web UI can poll it while a 1000-number batch runs.
"""

import csv
import io
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .india import normalize_msisdn, to_e164
from .providers import get_provider, LookupResult, STATUS_INVALID, STATUS_ERROR


class _RateLimiter:
    """Token-ish limiter: at most ``rate`` starts per second across threads."""

    def __init__(self, rate_per_sec: float):
        self._min_interval = (1.0 / rate_per_sec) if rate_per_sec and rate_per_sec > 0 else 0.0
        self._lock = threading.Lock()
        self._next_time = 0.0

    def acquire(self):
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_time - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_time = max(now, self._next_time) + self._min_interval


class BulkJob:
    """One bulk-lookup run. Thread-safe progress + results."""

    def __init__(self, raw_numbers, concurrency=10, rate_per_sec=8.0, provider=None):
        self.id = uuid.uuid4().hex[:12]
        self.created_at = time.time()
        self.started_at = None
        self.finished_at = None
        self.status = "pending"          # pending | running | done | error
        self.concurrency = max(1, int(concurrency))
        self.rate_per_sec = float(rate_per_sec)
        self._provider = provider or get_provider()
        self.provider_name = getattr(self._provider, "name", "unknown")

        self._lock = threading.Lock()
        self.results = []                # list[LookupResult]
        self.invalid = []               # list[{"input":..., "reason":...}]
        self._cancel = threading.Event()

        # Normalise + de-duplicate, keeping the original input for the report.
        seen = {}
        total_raw = 0
        for raw in raw_numbers:
            raw = (raw or "").strip()
            if not raw:
                continue
            total_raw += 1
            n = normalize_msisdn(raw)
            if n is None:
                self.invalid.append({"input": raw, "reason": "not a valid Indian mobile number"})
                continue
            # De-dup on the normalised number; remember first raw form.
            seen.setdefault(n, raw)

        self.total_input = total_raw
        self.numbers = list(seen.keys())   # unique valid numbers to look up
        self.total = len(self.numbers)
        self.duplicates = total_raw - self.total - len(self.invalid)
        self.completed = 0

    # ── progress ────────────────────────────────────────────────────────────
    def cancel(self):
        self._cancel.set()

    def progress(self):
        with self._lock:
            done = self.completed
        pct = (done / self.total * 100.0) if self.total else 100.0
        return {
            "id": self.id,
            "status": self.status,
            "provider": self.provider_name,
            "total_input": self.total_input,
            "unique": self.total,
            "duplicates": self.duplicates,
            "invalid": len(self.invalid),
            "completed": done,
            "percent": round(pct, 1),
            "elapsed": round((self.finished_at or time.time()) - (self.started_at or time.time()), 1)
                       if self.started_at else 0.0,
        }

    # ── execution ─────────────────────────────────────────────────────────────
    def run(self):
        self.status = "running"
        self.started_at = time.time()
        limiter = _RateLimiter(self.rate_per_sec)

        def _one(number):
            if self._cancel.is_set():
                return None
            limiter.acquire()
            try:
                return self._provider.lookup(number)
            except Exception as exc:
                r = LookupResult(msisdn=number, e164=to_e164(number),
                                 status=STATUS_ERROR, source=self.provider_name)
                r.error = f"{type(exc).__name__}: {exc}"
                return r

        try:
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                futures = {pool.submit(_one, n): n for n in self.numbers}
                for fut in as_completed(futures):
                    res = fut.result()
                    with self._lock:
                        if res is not None:
                            self.results.append(res)
                        self.completed += 1
            self.status = "done" if not self._cancel.is_set() else "cancelled"
        except Exception as exc:
            self.status = "error"
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.finished_at = time.time()

    def run_async(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

    # ── reporting ─────────────────────────────────────────────────────────────
    def summary(self):
        counts = {}
        operators = {}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
            if r.valid and r.current_operator:
                operators[r.current_operator] = operators.get(r.current_operator, 0) + 1
        ported = sum(1 for r in self.results if r.is_ported)
        return {
            "by_status": counts,
            "by_operator": operators,
            "ported": ported,
            "valid": sum(1 for r in self.results if r.valid),
            "errors": counts.get(STATUS_ERROR, 0),
        }

    def to_csv(self) -> str:
        fields = ["msisdn", "e164", "status", "valid", "reachable",
                  "current_operator", "original_operator", "is_ported",
                  "roaming", "mccmnc", "imsi", "country", "source", "error"]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in self.results:
            row = r.as_dict()
            row.pop("checked_at", None)
            w.writerow(row)
        # Append invalid inputs so nothing is silently dropped.
        for bad in self.invalid:
            w.writerow({"msisdn": bad["input"], "status": STATUS_INVALID,
                        "valid": False, "error": bad["reason"], "source": "validator"})
        return buf.getvalue()


class JobStore:
    """In-memory registry of jobs (most-recent-first), with a size cap."""

    def __init__(self, max_jobs=50):
        self._jobs = {}
        self._order = []
        self._max = max_jobs
        self._lock = threading.Lock()

    def add(self, job: BulkJob):
        with self._lock:
            self._jobs[job.id] = job
            self._order.insert(0, job.id)
            while len(self._order) > self._max:
                old = self._order.pop()
                self._jobs.pop(old, None)
        return job

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self, n=10):
        with self._lock:
            return [self._jobs[i] for i in self._order[:n] if i in self._jobs]
