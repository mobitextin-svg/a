#!/usr/bin/env python3
"""
Browser automation for number lookup on e164.com (or a similar site).

Your flow:
  1. Read phone numbers from an uploaded Excel file (.xlsx).
  2. Open https://www.e164.com in a real browser (Playwright / Chromium).
  3. For each number, one by one: paste it into the search box, let the site
     search, and read the "Results for: …" block.
  4. Save every result to a Notepad (.txt) file  (also supports .xlsx / .csv —
     the format is picked from the -o file extension).

Results are written after every number, so a stop halfway loses nothing; resume
with --start N.

e164.com returns these fields, which this script parses out:
  Prefix, Calling Code, ISO3, TADIG, MCCMNC, Type, Location,
  Operator Brand, Operator Company, Operator Group,
  Total Length Min, Total Length Max, Weight, Source

Setup (on the machine that CAN reach e164.com):
    pip install playwright openpyxl
    playwright install chromium

Examples:
    # Excel in -> Notepad out, headed so you can watch:
    python playwright_lookup.py -i numbers.xlsx -o results.txt --headed

    # pause once for any login/CAPTCHA, be polite between numbers:
    python playwright_lookup.py -i numbers.xlsx -o results.txt --headed \
        --pause-first --delay 2
"""

import os
import re
import csv
import sys
import time
import argparse

try:
    from openpyxl import load_workbook, Workbook
except ImportError:
    sys.exit("Missing 'openpyxl'. Run: pip install openpyxl")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sys.exit("Missing 'playwright'. Run: pip install playwright && playwright install chromium")

try:
    from hlr.india import normalize_msisdn, to_e164
except Exception:  # allow running standalone
    def normalize_msisdn(raw):
        d = re.sub(r"\D", "", raw or "")
        if d.startswith("0091"): d = d[4:]
        elif d.startswith("91") and len(d) == 12: d = d[2:]
        elif d.startswith("0") and len(d) == 11: d = d[1:]
        return d if len(d) == 10 and d[0] in "6789" else None
    def to_e164(n): return "+91" + n


# The exact labels e164.com prints, in display order.
E164_FIELDS = [
    "Prefix", "Calling Code", "ISO3", "TADIG", "MCCMNC", "Type", "Location",
    "Operator Brand", "Operator Company", "Operator Group",
    "Total Length Min", "Total Length Max", "Weight", "Source",
]

SEARCH_GUESSES = [
    "input[type=search]", "input[type=tel]",
    "input[name*=number i]", "input[id*=number i]",
    "input[name*=phone i]", "input[id*=phone i]",
    "input[name*=search i]", "input[id*=search i]",
    "input[placeholder*=number i]", "input[placeholder*=phone i]",
    "input[type=text]:visible", "input:visible",
]


# ── Excel input ─────────────────────────────────────────────────────────────
def read_numbers(path, column):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]

    col_idx = None
    if column:
        col = column.strip()
        if col.lower() in header:
            col_idx = header.index(col.lower())
        elif re.fullmatch(r"[A-Za-z]", col):
            col_idx = ord(col.upper()) - ord("A")
        elif col.isdigit():
            col_idx = int(col)
    if col_idx is None:
        for i, h in enumerate(header):
            if any(k in h for k in ("number", "phone", "msisdn", "mobile", "cell")):
                col_idx = i
                break
        if col_idx is None:
            col_idx = 0

    header_is_label = not re.search(r"\d", str(rows[0][col_idx] or ""))
    body = rows[1:] if header_is_label else rows
    out = []
    for r in body:
        if col_idx < len(r) and r[col_idx] not in (None, ""):
            out.append(str(r[col_idx]).strip())
    return out


# ── Result parsing ──────────────────────────────────────────────────────────
def parse_e164_result(body_text):
    """Pull the labelled e164.com fields out of the page's visible text."""
    fields = {}
    for label in E164_FIELDS:
        m = re.search(rf"(?m)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", body_text)
        if m:
            fields[label] = m.group(1).strip()
    return fields


def shown_number(body_text):
    """Digits from the 'Results for: …' line, or '' if not present."""
    m = re.search(r"Results for:\s*([0-9+\s]+)", body_text)
    return re.sub(r"\D", "", m.group(1)) if m else ""


# ── Output writers (chosen by file extension) ───────────────────────────────
COLUMNS = ["input", "msisdn", "typed"] + E164_FIELDS + ["status", "error", "checked_at"]


class NotepadWriter:
    """Human-readable .txt, one block per number."""

    def __init__(self, path):
        self.path = path
        self.fh = open(path, "w", encoding="utf-8")
        self.fh.write("HLR / number lookup results — source: e164.com\n")
        self.fh.write("Generated: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        self.fh.flush()

    def add(self, rec):
        f = self.fh
        f.write("\n" + "=" * 56 + "\n")
        typed = rec.get("typed") or ""
        f.write(f"Input: {rec.get('input','')}"
                + (f"   (typed: {typed})" if typed else "") + "\n")
        if rec.get("status") == "INVALID":
            f.write("  INVALID — not a valid Indian mobile number\n")
        elif rec.get("error"):
            f.write(f"  ERROR — {rec['error']}\n")
        else:
            for label in E164_FIELDS:
                if rec.get(label):
                    f.write(f"  {label}: {rec[label]}\n")
        f.write(f"  Checked: {rec.get('checked_at','')}\n")
        f.flush()

    def close(self):
        self.fh.close()


class CsvWriter:
    def __init__(self, path):
        self.fh = open(path, "w", encoding="utf-8", newline="")
        self.w = csv.DictWriter(self.fh, fieldnames=COLUMNS, extrasaction="ignore")
        self.w.writeheader()
        self.fh.flush()

    def add(self, rec):
        self.w.writerow(rec)
        self.fh.flush()

    def close(self):
        self.fh.close()


class ExcelWriter:
    def __init__(self, path):
        self.path = path
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "results"
        self.ws.append(COLUMNS)
        self.wb.save(path)

    def add(self, rec):
        self.ws.append([rec.get(c, "") for c in COLUMNS])
        self.wb.save(self.path)

    def close(self):
        self.wb.save(self.path)


def make_writer(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ""):
        return NotepadWriter(path)
    if ext == ".csv":
        return CsvWriter(path)
    if ext in (".xlsx", ".xlsm"):
        return ExcelWriter(path)
    # default to notepad
    return NotepadWriter(path)


# ── Automation ──────────────────────────────────────────────────────────────
def find_search_box(page, selector):
    if selector:
        return page.locator(selector).first
    for guess in SEARCH_GUESSES:
        loc = page.locator(guess).first
        try:
            if loc.count() and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def do_one(page, typed, national, args):
    """Search one number on an already-loaded page. Returns (fields, body, err)."""
    if args.reload_each:
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)

    box = find_search_box(page, args.search_selector)
    if box is None:
        return {}, "", "search box not found (set --search-selector)"

    box.click()
    box.fill("")
    # Type it so the site's live/reactive search fires (fill alone can be missed).
    box.press_sequentially(typed, delay=15)

    # Nudge sites that need Enter or a button; harmless if the site is reactive.
    if args.submit_selector:
        try:
            page.locator(args.submit_selector).first.click(timeout=3000)
        except Exception:
            pass
    else:
        try:
            box.press("Enter")
        except Exception:
            pass

    # Wait until the "Results for: …" block reflects THIS number (not the last).
    deadline = time.time() + args.timeout / 1000.0
    body = ""
    while time.time() < deadline:
        body = page.inner_text("body")
        if national and national in shown_number(body):
            break
        page.wait_for_timeout(200)
    else:
        return {}, body, "timed out waiting for this number's result"

    page.wait_for_timeout(args.settle)
    body = page.inner_text("body")
    fields = parse_e164_result(body)
    if not fields:
        return {}, body, "results block not found / no fields parsed"
    return fields, body, ""


def main():
    ap = argparse.ArgumentParser(description="Excel numbers -> e164.com lookup -> Notepad/Excel/CSV.")
    ap.add_argument("-i", "--input", required=True, help="input .xlsx with the numbers")
    ap.add_argument("-o", "--output", default="results.txt",
                    help="output file; .txt=Notepad (default), .xlsx=Excel, .csv=CSV")
    ap.add_argument("-c", "--column", default="", help="column header/letter holding numbers (auto if omitted)")
    ap.add_argument("--url", default="https://www.e164.com", help="lookup website URL")
    ap.add_argument("--search-selector", default="", help="CSS selector for the search box")
    ap.add_argument("--submit-selector", default="", help="CSS selector for a search button (Enter used if omitted)")
    ap.add_argument("--number-format", choices=["cc", "e164", "national", "raw"], default="cc",
                    help="what to type: cc=91XXXXXXXXXX (matches e164.com), e164=+91…, national=10-digit, raw=cell")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--pause-first", action="store_true", help="pause after first load for manual login/CAPTCHA")
    ap.add_argument("--reload-each", action="store_true", help="reload the page before every number")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between numbers (be polite)")
    ap.add_argument("--settle", type=int, default=600, help="ms to wait after result appears before reading")
    ap.add_argument("--timeout", type=int, default=30000, help="per-number wait timeout (ms)")
    ap.add_argument("--slowmo", type=int, default=0, help="slow every action by N ms (debugging)")
    ap.add_argument("--start", type=int, default=0, help="skip the first N numbers (resume)")
    ap.add_argument("--limit", type=int, default=0, help="only process N numbers (0 = all)")
    ap.add_argument("--user-data-dir", default="", help="persist login/session in this folder")
    ap.add_argument("--executable-path", default=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
                    help="path to a specific Chromium binary (rarely needed)")
    args = ap.parse_args()

    raw_numbers = read_numbers(args.input, args.column)
    if not raw_numbers:
        sys.exit("No numbers found in the input file.")
    if args.start:
        raw_numbers = raw_numbers[args.start:]
    if args.limit:
        raw_numbers = raw_numbers[:args.limit]
    print(f"Loaded {len(raw_numbers)} numbers. Output -> {args.output}")

    writer = make_writer(args.output)

    with sync_playwright() as p:
        launch_kwargs = dict(headless=not args.headed, slow_mo=args.slowmo)
        if args.executable_path:
            launch_kwargs["executable_path"] = args.executable_path
        if args.user_data_dir:
            ctx = p.chromium.launch_persistent_context(args.user_data_dir, **launch_kwargs)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            browser = None
        else:
            browser = p.chromium.launch(**launch_kwargs)
            ctx = browser.new_context()
            page = ctx.new_page()

        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
        if args.pause_first and args.headed:
            print("Paused. Log in / clear any CAPTCHA in the window, then press Enter here…")
            try:
                input()
            except EOFError:
                page.pause()

        ok = err = 0
        for idx, raw in enumerate(raw_numbers, start=1 + args.start):
            n = normalize_msisdn(raw)
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            if args.number_format == "raw":
                typed = re.sub(r"\s+", "", raw)
                national = re.sub(r"\D", "", raw)[-10:]
            elif n is None:
                writer.add({"input": raw, "status": "INVALID",
                            "error": "invalid Indian mobile number", "checked_at": now})
                err += 1
                print(f"[{idx}] {raw}: INVALID (skipped)")
                continue
            elif args.number_format == "e164":
                typed, national = to_e164(n), n
            elif args.number_format == "national":
                typed, national = n, n
            else:  # cc -> 91XXXXXXXXXX (matches what e164.com echoes)
                typed, national = "91" + n, n

            try:
                fields, _body, err_msg = do_one(page, typed, national, args)
            except Exception as exc:
                fields, err_msg = {}, f"{type(exc).__name__}: {exc}"

            rec = {"input": raw, "msisdn": (n or ""), "typed": typed,
                   "status": ("OK" if fields and not err_msg else "ERROR"),
                   "error": err_msg, "checked_at": now}
            rec.update(fields)
            writer.add(rec)

            if err_msg:
                err += 1
                print(f"[{idx}] {typed}: ERROR — {err_msg}")
            else:
                ok += 1
                op = fields.get("Operator Brand", "?")
                print(f"[{idx}] {typed}: {op} | MCCMNC {fields.get('MCCMNC','?')} | {fields.get('Type','?')}")

            if args.delay:
                time.sleep(args.delay)

        (ctx if args.user_data_dir else browser).close()

    writer.close()
    print(f"\nDone. {ok} ok, {err} error/invalid. Saved to {args.output}")


if __name__ == "__main__":
    main()
