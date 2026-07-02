"""
Bulk HLR Lookup — web app + JSON API for checking Indian mobile numbers.

Run:
    pip install -r requirements.txt
    python app.py
    # open http://127.0.0.1:5000

By default it uses the offline MockProvider so you can test the full pipeline
(paste 1000 numbers, watch progress, export CSV) without any API key. To use a
real HLR gateway, set the HLR_PROVIDER=http env vars documented in
hlr/providers.py.
"""

import os
import io
import sys

_MISSING = []
try:
    from flask import (Flask, request, render_template, jsonify,
                       send_file, abort, Response)
except ImportError:
    _MISSING.append("flask")

if _MISSING:
    print("\n  ERROR: missing packages: " + ", ".join(_MISSING))
    print("  Install them with:  pip install -r requirements.txt\n")
    sys.exit(1)

from hlr import BulkJob, JobStore
from hlr.india import normalize_msisdn, to_e164, guess_operator
from hlr.providers import get_provider

app = Flask(__name__)
STORE = JobStore(max_jobs=int(os.environ.get("HLR_MAX_JOBS", "50")))

# Safety caps so a paste-bomb can't exhaust the box.
MAX_NUMBERS = int(os.environ.get("HLR_MAX_NUMBERS", "5000"))
DEFAULT_CONCURRENCY = int(os.environ.get("HLR_CONCURRENCY", "10"))
DEFAULT_RATE = float(os.environ.get("HLR_RATE_PER_SEC", "8"))


def _parse_numbers(text, file_storage):
    """Collect raw number strings from a textarea and/or an uploaded file."""
    raw = []
    if text:
        raw.extend(_split(text))
    if file_storage and file_storage.filename:
        data = file_storage.read().decode("utf-8", errors="ignore")
        # Works for .txt and simple .csv (splits on commas and newlines).
        raw.extend(_split(data))
    return raw


def _split(blob):
    out = []
    for line in blob.replace("\r", "\n").split("\n"):
        for part in line.split(","):
            part = part.strip().strip('"').strip("'")
            if part:
                out.append(part)
    return out


@app.route("/")
def index():
    return render_template("index.html",
                           provider=os.environ.get("HLR_PROVIDER", "mock"),
                           max_numbers=MAX_NUMBERS,
                           recent=STORE.recent(8))


@app.route("/api/lookup", methods=["POST"])
def api_single():
    """Look up one number synchronously. Body: {"number": "9876543210"}."""
    payload = request.get_json(silent=True) or {}
    raw = (payload.get("number") or request.form.get("number") or "").strip()
    n = normalize_msisdn(raw)
    if n is None:
        return jsonify({"ok": False, "error": "invalid Indian mobile number",
                        "input": raw}), 400
    result = get_provider().lookup(n)
    return jsonify({"ok": True, "result": result.as_dict()})


@app.route("/api/validate", methods=["POST"])
def api_validate():
    """Validate/normalise numbers without doing any lookup (free + instant)."""
    payload = request.get_json(silent=True) or {}
    raw_list = payload.get("numbers") or _split(payload.get("text", ""))
    valid, invalid = [], []
    for raw in raw_list:
        n = normalize_msisdn(str(raw))
        if n:
            valid.append({"input": raw, "msisdn": n, "e164": to_e164(n),
                          "operator_hint": guess_operator(n)})
        else:
            invalid.append(raw)
    return jsonify({"ok": True, "valid": valid, "invalid": invalid,
                    "valid_count": len(valid), "invalid_count": len(invalid)})


@app.route("/api/jobs", methods=["POST"])
def api_start_job():
    """Start a bulk lookup. Accepts form 'numbers' text and/or a file upload."""
    text = request.form.get("numbers", "")
    file_storage = request.files.get("file")
    concurrency = int(request.form.get("concurrency", DEFAULT_CONCURRENCY))
    rate = float(request.form.get("rate", DEFAULT_RATE))

    raw = _parse_numbers(text, file_storage)
    if not raw:
        return jsonify({"ok": False, "error": "no numbers provided"}), 400
    if len(raw) > MAX_NUMBERS:
        return jsonify({"ok": False,
                        "error": f"too many numbers ({len(raw)}); max {MAX_NUMBERS}"}), 400

    job = BulkJob(raw, concurrency=concurrency, rate_per_sec=rate)
    if job.total == 0:
        return jsonify({"ok": False, "error": "no valid Indian mobile numbers found",
                        "invalid": job.invalid[:20]}), 400
    STORE.add(job)
    job.run_async()
    return jsonify({"ok": True, "job": job.progress()})


@app.route("/api/jobs/<job_id>")
def api_job_status(job_id):
    job = STORE.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({"ok": True, "job": job.progress(), "summary": job.summary()})


@app.route("/api/jobs/<job_id>/results")
def api_job_results(job_id):
    job = STORE.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({
        "ok": True,
        "job": job.progress(),
        "summary": job.summary(),
        "results": [r.as_dict() for r in job.results],
        "invalid": job.invalid,
    })


@app.route("/api/jobs/<job_id>/export.csv")
def api_job_csv(job_id):
    job = STORE.get(job_id)
    if not job:
        abort(404)
    csv_data = job.to_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=hlr_{job_id}.csv"},
    )


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def api_job_cancel(job_id):
    job = STORE.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    job.cancel()
    return jsonify({"ok": True, "job": job.progress()})


@app.route("/results/<job_id>")
def results_page(job_id):
    job = STORE.get(job_id)
    if not job:
        abort(404)
    return render_template("results.html", job_id=job_id)


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "provider": os.environ.get("HLR_PROVIDER", "mock")})


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  Bulk HLR Lookup running at http://{host}:{port}")
    print(f"  Provider: {os.environ.get('HLR_PROVIDER', 'mock')}  "
          f"(set HLR_PROVIDER=http for a real gateway)\n")
    app.run(host=host, port=port, debug=os.environ.get("DEBUG") == "1", threaded=True)
