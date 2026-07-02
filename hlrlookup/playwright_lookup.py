#!/usr/bin/env python3
"""
Browser automation for HLR / number lookup on a website (default: e164.com).

What it does, per your request:
  1. Reads phone numbers from an uploaded Excel file (.xlsx).
  2. Opens the lookup website in a real browser (Playwright / Chromium).
  3. For each number, one by one: types it into the search box, clicks Search,
     waits for the result, and copies the result text.
  4. Writes the results back into an Excel file (one row per number).

Results are saved after every number, so if it stops halfway nothing is lost
and you can resume with --start.

────────────────────────────────────────────────────────────────────────────
IMPORTANT — selectors
The exact search-box / button / result location on the site can't be guessed
reliably. The script auto-detects a likely search box, but for a solid run set
the three selectors explicitly (see "Finding selectors" in the README). You get
them in 30 seconds with:  playwright codegen https://www.e164.com
────────────────────────────────────────────────────────────────────────────

Setup (on the machine that CAN reach the site):
    pip install playwright openpyxl
    playwright install chromium

Examples:
    # headed (watch it), auto-detect the search box:
    python playwright_lookup.py -i numbers.xlsx -o results.xlsx --headed

    # explicit selectors + pause once for manual login/CAPTCHA:
    python playwright_lookup.py -i numbers.xlsx -o results.xlsx --headed \
        --search-selector "#phone" --submit-selector "button[type=submit]" \
        --result-selector "#result" --pause-first
"""

import os
import re
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

# Reuse the Indian-number normaliser from the sibling package when available.
try:
    from hlr.india import normalize_msisdn, to_e164
except Exception:  # pragma: no cover - allow running the file standalone
    def normalize_msisdn(raw):
        d = re.sub(r"\D", "", raw or "")
        if d.startswith("0091"): d = d[4:]
        elif d.startswith("91") and len(d) == 12: d = d[2:]
        elif d.startswith("0") and len(d) == 11: d = d[1:]
        return d if len(d) == 10 and d[0] in "6789" else None
    def to_e164(n): return "+91" + n


# Common search-box guesses, tried in order when --search-selector is absent.
SEARCH_GUESSES = [
    "input[type=search]",
    "input[name*=number i]", "input[id*=number i]",
    "input[name*=msisdn i]", "input[id*=msisdn i]",
    "input[name*=phone i]", "input[id*=phone i]",
    "input[name*=search i]", "input[id*=search i]",
    "input[placeholder*=number i]", "input[placeholder*=search i]",
    "input[type=tel]", "input[type=text]:visible", "textarea:visible",
]


# ── Excel helpers ───────────────────────────────────────────────────────────
def read_numbers(path, column):
    """Read numbers from an .xlsx. ``column`` may be a header name or a letter/index."""
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
        elif re.fullmatch(r"[A-Za-z]", col):        # a column letter like "A"
            col_idx = ord(col.upper()) - ord("A")
        elif col.isdigit():
            col_idx = int(col)
    if col_idx is None:
        # Auto-pick: a column whose header mentions number/phone/msisdn/mobile,
        # else the first column.
        for i, h in enumerate(header):
            if any(k in h for k in ("number", "phone", "msisdn", "mobile", "cell")):
                col_idx = i
                break
        if col_idx is None:
            col_idx = 0

    header_is_label = not re.search(r"\d", str(rows[0][col_idx] or ""))
    body = rows[1:] if header_is_label else rows
    numbers = []
    for r in body:
        if col_idx < len(r) and r[col_idx] not in (None, ""):
            numbers.append(str(r[col_idx]).strip())
    return numbers


class ResultWriter:
    """Incrementally writes results to an .xlsx, saving after each row."""

    HEADERS = ["input", "msisdn", "e164", "result", "status", "error", "checked_at"]

    def __init__(self, path):
        self.path = path
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "results"
        self.ws.append(self.HEADERS)
        self.wb.save(path)

    def add(self, **row):
        self.ws.append([row.get(h, "") for h in self.HEADERS])
        self.wb.save(self.path)   # durable: survive a crash mid-run


# ── the automation ──────────────────────────────────────────────────────────
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


def do_one(page, number_to_type, args):
    """Run a single lookup on an already-loaded page. Returns (result_text, err)."""
    # Re-navigate each iteration if requested (safest for non-SPA sites).
    if args.reload_each:
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)

    box = find_search_box(page, args.search_selector)
    if box is None:
        return "", "search box not found (set --search-selector)"

    box.click()
    box.fill("")
    box.fill(number_to_type)

    # Submit: explicit button, else a Search-labelled button, else Enter.
    submitted = False
    if args.submit_selector:
        try:
            page.locator(args.submit_selector).first.click(timeout=5000)
            submitted = True
        except Exception:
            pass
    if not submitted:
        try:
            page.get_by_role("button", name=re.compile("search|lookup|check", re.I)).first.click(timeout=3000)
            submitted = True
        except Exception:
            pass
    if not submitted:
        box.press("Enter")

    # Wait for the result to appear.
    try:
        if args.result_selector:
            page.locator(args.result_selector).first.wait_for(state="visible", timeout=args.timeout)
            page.wait_for_timeout(args.settle)
            text = page.locator(args.result_selector).first.inner_text()
        else:
            page.wait_for_load_state("networkidle", timeout=args.timeout)
            page.wait_for_timeout(args.settle)
            text = page.inner_text("body")
    except PWTimeout:
        return "", "timed out waiting for result"

    return " ".join(text.split()), ""


def main():
    ap = argparse.ArgumentParser(description="Excel → website lookup → Excel, via Playwright.")
    ap.add_argument("-i", "--input", required=True, help="input .xlsx with the numbers")
    ap.add_argument("-o", "--output", default="results.xlsx", help="output .xlsx")
    ap.add_argument("-c", "--column", default="", help="column header/letter holding numbers (auto if omitted)")
    ap.add_argument("--url", default="https://www.e164.com", help="lookup website URL")
    ap.add_argument("--search-selector", default="", help="CSS selector for the search box")
    ap.add_argument("--submit-selector", default="", help="CSS selector for the search button")
    ap.add_argument("--result-selector", default="", help="CSS selector for the result element")
    ap.add_argument("--number-format", choices=["e164", "national", "raw"], default="e164",
                    help="what to type: +91XXXXXXXXXX (e164), 10-digit (national), or the raw cell (raw)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--pause-first", action="store_true", help="pause after first load for manual login/CAPTCHA")
    ap.add_argument("--reload-each", action="store_true", help="reload the page before every number")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds to wait between numbers (be polite)")
    ap.add_argument("--settle", type=int, default=800, help="ms to wait after result appears before reading")
    ap.add_argument("--timeout", type=int, default=30000, help="per-step timeout (ms)")
    ap.add_argument("--slowmo", type=int, default=0, help="slow every action by N ms (debugging)")
    ap.add_argument("--start", type=int, default=0, help="skip the first N numbers (resume)")
    ap.add_argument("--limit", type=int, default=0, help="only process N numbers (0 = all)")
    ap.add_argument("--user-data-dir", default="", help="persist login/session in this folder")
    ap.add_argument("--executable-path", default=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
                    help="path to a specific Chromium binary (usually not needed after "
                         "'playwright install chromium'); or set PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    args = ap.parse_args()

    raw_numbers = read_numbers(args.input, args.column)
    if not raw_numbers:
        sys.exit("No numbers found in the input file.")
    if args.start:
        raw_numbers = raw_numbers[args.start:]
    if args.limit:
        raw_numbers = raw_numbers[:args.limit]
    print(f"Loaded {len(raw_numbers)} numbers. Output → {args.output}")

    writer = ResultWriter(args.output)

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
        if args.pause_first:
            if args.headed:
                print("Paused. Log in / clear any CAPTCHA in the window, then press Enter here…")
                try:
                    input()
                except EOFError:
                    page.pause()
            else:
                print("--pause-first needs --headed; continuing without pause.")

        ok = err_count = 0
        for idx, raw in enumerate(raw_numbers, start=1 + args.start):
            n = normalize_msisdn(raw)
            if args.number_format == "raw":
                to_type = raw
            elif n is None:
                writer.add(input=raw, error="invalid Indian mobile number", status="INVALID",
                           checked_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                err_count += 1
                print(f"[{idx}] {raw}: INVALID (skipped)")
                continue
            elif args.number_format == "e164":
                to_type = to_e164(n)
            else:
                to_type = n

            try:
                result, err = do_one(page, to_type, args)
            except Exception as exc:
                result, err = "", f"{type(exc).__name__}: {exc}"

            writer.add(
                input=raw, msisdn=(n or ""), e164=(to_e164(n) if n else ""),
                result=result, status=("OK" if result and not err else "ERROR"),
                error=err, checked_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            if err:
                err_count += 1
                print(f"[{idx}] {to_type}: ERROR — {err}")
            else:
                ok += 1
                print(f"[{idx}] {to_type}: {result[:80]}")

            if args.delay:
                time.sleep(args.delay)

        (ctx if args.user_data_dir else browser).close()

    print(f"\nDone. {ok} ok, {err_count} error/invalid. Saved to {args.output}")


if __name__ == "__main__":
    main()
