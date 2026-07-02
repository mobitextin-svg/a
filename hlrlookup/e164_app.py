"""
Real-data e164.com lookup — web app.

Paste or upload Indian mobile numbers; this app drives a REAL browser against
https://www.e164.com (via Playwright), reads each result, and shows the real
e164.com fields in a table you can download as CSV or TXT.

There is NO mock/synthetic data here — every row comes from e164.com.

Run (on a machine that can reach e164.com):
    pip install -r requirements-playwright.txt flask
    playwright install chromium
    python e164_app.py            # → http://127.0.0.1:5000

Notes:
  * Lookups run sequentially in one browser (polite to the site). 1000 numbers
    at ~2s each is ~30–40 min — that's the nature of live scraping, not a bug.
  * Set HEADFUL=1 to watch the browser (useful the first time / for CAPTCHAs).
"""

import os
import sys
import time
import uuid
import threading

try:
    from flask import Flask, request, jsonify, render_template_string, Response, abort
except ImportError:
    sys.exit("Missing Flask. Run: pip install flask")

from hlr.e164_scrape import (
    E164Scraper, read_numbers, split_text, format_typed,
    COLUMNS, E164_FIELDS, rows_to_csv, rows_to_txt,
)

app = Flask(__name__)
JOBS = {}
JOBS_LOCK = threading.Lock()
MAX_NUMBERS = int(os.environ.get("HLR_MAX_NUMBERS", "5000"))


class Job:
    def __init__(self, raw_numbers, number_format="cc"):
        self.id = uuid.uuid4().hex[:12]
        self.raw = raw_numbers
        self.number_format = number_format
        self.total = len(raw_numbers)
        self.done = 0
        self.status = "running"      # running | done | error | stopped
        self.rows = []
        self.error = ""
        self._stop = threading.Event()
        self.lock = threading.Lock()

    def stop(self):
        self._stop.set()

    def progress(self):
        with self.lock:
            return {"id": self.id, "status": self.status, "total": self.total,
                    "done": self.done, "ok": sum(1 for r in self.rows if r.get("status") == "OK"),
                    "errors": sum(1 for r in self.rows if r.get("status") in ("ERROR", "INVALID"))}

    def run(self):
        headless = os.environ.get("HEADFUL", "0") != "1"
        try:
            with E164Scraper(
                url=os.environ.get("E164_URL", "https://www.e164.com"),
                search_selector=os.environ.get("E164_SEARCH_SELECTOR", ""),
                submit_selector=os.environ.get("E164_SUBMIT_SELECTOR", ""),
                headless=headless,
                executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
            ) as sc:
                for raw in self.raw:
                    if self._stop.is_set():
                        break
                    now = time.strftime("%Y-%m-%d %H:%M:%S")
                    typed, national, bad = format_typed(raw, self.number_format)
                    if bad:
                        row = {"input": raw, "status": "INVALID", "error": bad, "checked_at": now}
                    else:
                        try:
                            fields, err = sc.lookup(typed, national)
                        except Exception as exc:
                            fields, err = {}, f"{type(exc).__name__}: {exc}"
                        row = {"input": raw, "msisdn": national or "", "typed": typed,
                               "status": "OK" if fields and not err else "ERROR",
                               "error": err, "checked_at": now}
                        row.update(fields)
                    with self.lock:
                        self.rows.append(row)
                        self.done += 1
                    time.sleep(float(os.environ.get("E164_DELAY", "1.5")))
            with self.lock:
                if self.status == "running":
                    self.status = "stopped" if self._stop.is_set() else "done"
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.error = f"{type(exc).__name__}: {exc}"


PAGE = """
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>e164.com bulk lookup (real data)</title>
<style>
:root{--bg:#0f172a;--card:#1e293b;--line:#334155;--fg:#e2e8f0;--muted:#94a3b8;--accent:#22c55e;--bad:#f87171;}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg)}
.wrap{max-width:1100px;margin:0 auto;padding:24px 18px 60px}
h1{font-size:1.5rem;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:18px}
textarea{width:100%;min-height:120px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px;font-family:ui-monospace,monospace}
input[type=file]{color:var(--fg)}
button{background:var(--accent);color:#04220f;border:0;border-radius:999px;padding:10px 22px;font-weight:700;cursor:pointer}
button.ghost{background:transparent;color:var(--fg);border:1px solid var(--line)}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px}
progress{width:100%;height:16px}
table{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:8px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);position:sticky;top:0;background:var(--card)}
.tablewrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.tag{padding:1px 8px;border-radius:999px;font-size:.72rem;font-weight:700}
.OK{background:rgba(34,197,94,.15);color:var(--accent)}.ERROR,.INVALID{background:rgba(248,113,113,.15);color:var(--bad)}
.note{color:var(--muted);font-size:.8rem}a{color:var(--accent)}
</style></head><body><div class="wrap">
<h1>e164.com bulk lookup <span class="note">· real data</span></h1>
<p class="sub">Reads each number straight from e164.com in a real browser. Fields shown are exactly what e164.com returns.</p>

<div class="card">
  <label class="note">Paste numbers (one per line or comma separated)</label>
  <textarea id="numbers" placeholder="9110097040&#10;9416659700"></textarea>
  <div class="row">
    <input type="file" id="file" accept=".xlsx,.csv,.txt">
    <button id="run">Start lookup</button>
    <button id="stop" class="ghost" style="display:none">Stop</button>
  </div>
  <p class="note">Sequential &amp; polite — 1000 numbers takes roughly half an hour. Keep this tab open.</p>
</div>

<div class="card" id="progressCard" style="display:none">
  <div class="row" style="justify-content:space-between">
    <strong id="pstatus">Running…</strong>
    <span class="note" id="pmeta"></span>
  </div>
  <progress id="bar" max="100" value="0"></progress>
  <div class="row">
    <a id="csv" href="#"><button class="ghost">Download CSV</button></a>
    <a id="txt" href="#"><button class="ghost">Download TXT (Notepad)</button></a>
  </div>
  <div class="tablewrap"><table>
    <thead><tr><th>Input</th><th>Status</th>{{fieldheads}}</tr></thead>
    <tbody id="rows"></tbody>
  </table></div>
</div>

<script>
const $=s=>document.querySelector(s);const FIELDS={{fields_json}};let job=null,timer=null;
$("#run").onclick=async()=>{
  const fd=new FormData();fd.append("numbers",$("#numbers").value);
  if($("#file").files[0])fd.append("file",$("#file").files[0]);
  const r=await fetch("/run",{method:"POST",body:fd}).then(r=>r.json());
  if(!r.ok){alert(r.error||"error");return;}
  job=r.id;$("#progressCard").style.display="block";$("#stop").style.display="inline-block";
  $("#csv").href="/download/"+job+".csv";$("#txt").href="/download/"+job+".txt";poll();
};
$("#stop").onclick=()=>fetch("/stop/"+job,{method:"POST"});
function poll(){clearTimeout(timer);
  fetch("/results/"+job).then(r=>r.json()).then(d=>{
    if(!d.ok)return;const p=d.progress;
    $("#pstatus").textContent=p.status[0].toUpperCase()+p.status.slice(1)+(p.status==="running"?"…":"");
    $("#pmeta").textContent=p.done+"/"+p.total+"  ·  "+p.ok+" ok, "+p.errors+" err";
    $("#bar").value=p.total?Math.round(p.done/p.total*100):0;
    $("#rows").innerHTML=d.rows.map(row=>{
      const cells=FIELDS.map(f=>"<td>"+(row[f]!=null?String(row[f]):"—")+"</td>").join("");
      return "<tr><td>"+(row.input||"")+"</td><td><span class='tag "+(row.status||"")+"'>"+(row.status||"")+"</span></td>"+cells+"</tr>";
    }).join("");
    if(["done","error","stopped"].includes(p.status)){$("#stop").style.display="none";}
    else{timer=setTimeout(poll,1000);}
  });
}
</script></div></body></html>
"""


def render():
    heads = "".join(f"<th>{f}</th>" for f in E164_FIELDS)
    import json
    return render_template_string(PAGE, fieldheads=heads, fields_json=json.dumps(E164_FIELDS))


@app.route("/")
def index():
    return render()


@app.route("/run", methods=["POST"])
def run():
    raw = split_text(request.form.get("numbers", ""))
    f = request.files.get("file")
    if f and f.filename:
        if f.filename.lower().endswith((".xlsx", ".xlsm")):
            tmp = os.path.join("/tmp", "upload_" + uuid.uuid4().hex + ".xlsx")
            f.save(tmp)
            try:
                raw += read_numbers(tmp)
            finally:
                try: os.remove(tmp)
                except OSError: pass
        else:
            raw += split_text(f.read().decode("utf-8", errors="ignore"))
    if not raw:
        return jsonify({"ok": False, "error": "no numbers provided"}), 400
    if len(raw) > MAX_NUMBERS:
        return jsonify({"ok": False, "error": f"too many numbers ({len(raw)}); max {MAX_NUMBERS}"}), 400

    job = Job(raw, number_format=request.form.get("number_format", "cc"))
    with JOBS_LOCK:
        JOBS[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return jsonify({"ok": True, "id": job.id, "total": job.total})


@app.route("/results/<job_id>")
def results(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    with job.lock:
        rows = list(job.rows)
    return jsonify({"ok": True, "progress": job.progress(), "rows": rows})


@app.route("/stop/<job_id>", methods=["POST"])
def stop(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    job.stop()
    return jsonify({"ok": True})


@app.route("/download/<job_id>.<fmt>")
def download(job_id, fmt):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    with job.lock:
        rows = list(job.rows)
    if fmt == "csv":
        return Response(rows_to_csv(rows), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=e164_{job_id}.csv"})
    if fmt == "txt":
        return Response(rows_to_txt(rows), mimetype="text/plain",
                        headers={"Content-Disposition": f"attachment; filename=e164_{job_id}.txt"})
    abort(404)


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  Real-data e164.com lookup  →  http://{host}:{port}")
    print("  (drives a real browser; set HEADFUL=1 to watch it)\n")
    app.run(host=host, port=port, threaded=True)
