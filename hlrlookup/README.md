# Bulk HLR Lookup — India

Check the status of Indian mobile numbers (+91) in bulk — up to a few thousand
at a time. For each number you get:

| Field | Meaning |
|-------|---------|
| `status` | `CONNECTED` (live/reachable), `ABSENT` (valid but off/out of coverage), `INVALID`, `ERROR`, `UNKNOWN` |
| `current_operator` | Network the number is on **now** (post-MNP) |
| `original_operator` | Network it was originally allocated to |
| `is_ported` | Whether it moved networks via Mobile Number Portability |
| `roaming` | Whether it's roaming off its home network |
| `mccmnc` | Mobile country + network code |

There's a **web app**, a **JSON API**, and a **command-line tool** — all on the
same core.

## Quick start (no API key needed)

```bash
cd hlrlookup
pip install -r requirements.txt
python app.py            # → http://127.0.0.1:5000
```

Out of the box it runs the **offline mock provider**: it exercises the whole
pipeline (paste 1000 numbers → normalise → de-dup → concurrent lookup → live
progress → CSV export) with deterministic synthetic data. Every mock row is
tagged `source="mock"` so it's never mistaken for real data. Click **"Load 1000
sample numbers"** in the UI to try it immediately.

Command line:

```bash
python cli.py sample_numbers.csv -o results.csv     # bulk, write CSV
python cli.py 9876543210 +91-9123456780             # a couple of numbers
```

## Using a real HLR gateway

Real HLR lookups require SS7 access, which you buy from a gateway (e.g.
hlr-lookups.com, Telnyx, or similar). Point the app at yours with env vars — no
code changes:

```bash
export HLR_PROVIDER=http
export HLR_API_URL="https://www.hlr-lookups.com/api/v2/hlr"   # your endpoint
export HLR_API_KEY="your-api-key"
# optional: adjust how the key is sent and how the JSON response maps
export HLR_API_KEY_HEADER="Authorization"     # or "" to send as a query param
export HLR_MAP_STATUS="hlr.status"            # dot-path into the JSON response
export HLR_MAP_CURRENT_OP="hlr.currentNetworkName"
python app.py
```

All configurable variables (endpoint, auth style, request format, and the full
response field mapping) are documented at the top of
[`hlr/providers.py`](hlr/providers.py). The `HttpProvider` normalises whatever
your gateway returns onto the common result shape above, so the UI, API and CSV
stay identical whether you're on mock or a live gateway.

> **Legal note:** HLR lookups involve personal data. Only look up numbers you're
> authorised to process, and comply with India's TRAI/DoT rules and applicable
> privacy law (e.g. the DPDP Act). This tool doesn't send SMS or calls — it only
> queries network signalling status via your chosen gateway.

## Browser automation (Excel → website → Excel)

If you'd rather drive the **e164.com website** directly instead of an API —
read numbers from an Excel file, type each into the site's search box, click
Search, and write the results back to Excel — use `playwright_lookup.py`. This
is the "one by one, paste into the search box" flow.

```bash
pip install -r requirements-playwright.txt
playwright install chromium         # one-time browser download

# make/prepare an input file (a "mobile_number" column)
python make_input_template.py -o numbers.xlsx        # then paste your numbers in

# run it (headed so you can watch / handle any login or CAPTCHA)
# output to a Notepad .txt file:
python playwright_lookup.py -i numbers.xlsx -o results.txt --headed
```

The **output format is chosen by the file extension**:
`-o results.txt` → Notepad file (default), `-o results.xlsx` → Excel,
`-o results.csv` → CSV. Rows/blocks are written after **every** number, so a
crash never loses finished work — resume with `--start N`.

For each number the script parses the exact fields e164.com returns:

```
========================================================
Input: 9416659700   (typed: 919416659700)
  Prefix: 919416
  Calling Code: 91
  ISO3: IND
  TADIG: INDWB
  MCCMNC: 40434
  Type: MOBILE
  Location: N/A
  Operator Brand: BSNL
  Operator Company: BSNL - Haryana
  Operator Group: N/A
  Total Length Min: 12
  Total Length Max: 12
  Weight: 11
  Source: e164.com
  Checked: 2026-07-02 21:05:06
```

`--number-format cc` (the default) types `91XXXXXXXXXX` — the form e164.com
echoes back. The script waits until the on-page "Results for: …" block matches
**this** number before reading, so it never records a stale result.

### If it can't find the search box

The script auto-detects the search box (works for e164.com's phone input). If a
future layout change breaks that, grab the exact selector in ~30s:

```bash
playwright codegen https://www.e164.com
```

Click the search box (and result area) — codegen prints the selectors — then:

```bash
python playwright_lookup.py -i numbers.xlsx -o results.txt --headed \
    --search-selector "#yourSearchBox" --result-selector "#resultArea" \
    --delay 2 --pause-first
```

Useful flags: `--pause-first` (pause once after load so you can log in / clear a
CAPTCHA), `--reload-each` (fresh page per number), `--delay` (seconds between
numbers — be polite and respect the site's terms), `--number-format`
(`cc` = 91…, `e164` = +91…, `national` = 10-digit, `raw` = the cell as-is),
`--user-data-dir` (persist a login between runs).

> **Heads-up:** e164.com is behind bot-protection and may require an account /
> login and rate-limit automated use. Run the script from **your own machine**
> (not a locked-down CI box), keep `--delay` sane, and make sure your use
> complies with the site's terms of service and applicable law. If the site
> blocks automation, the API route above (with a proper HLR provider) is the
> robust option.

## JSON API

| Method & path | Purpose |
|---------------|---------|
| `POST /api/lookup` | One number, synchronous. Body `{"number": "9876543210"}` |
| `POST /api/validate` | Normalise/validate numbers only (free, no lookup) |
| `POST /api/jobs` | Start a bulk job. Form field `numbers` (text) and/or `file` upload |
| `GET /api/jobs/<id>` | Live progress + summary |
| `GET /api/jobs/<id>/results` | Full results JSON |
| `GET /api/jobs/<id>/export.csv` | Download results as CSV |
| `POST /api/jobs/<id>/cancel` | Cancel a running job |

Example:

```bash
curl -X POST localhost:5000/api/jobs -F "file=@sample_numbers.csv" -F "concurrency=25"
```

## Configuration (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `HLR_PROVIDER` | `mock` | `mock` or `http` |
| `HLR_CONCURRENCY` | `10` | Default worker threads per job |
| `HLR_RATE_PER_SEC` | `8` | Default lookups/sec rate cap (respect your gateway's limit) |
| `HLR_MAX_NUMBERS` | `5000` | Hard cap per job |
| `HLR_MOCK_LATENCY` | `0` | Fake per-lookup delay (seconds) for realistic demos |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Bind address |

## Number handling

Accepted input forms all normalise to a 10-digit national number:
`9876543210`, `09876543210`, `919876543210`, `+91 98765 43210`, `0091-9876543210`.
Valid Indian mobiles are 10 digits starting with 6, 7, 8 or 9. Inputs are
de-duplicated (on the normalised number) before lookup, and invalid inputs are
reported in the results rather than silently dropped.

## Tests

```bash
python test_hlr.py         # or: python -m pytest -q
```

## Layout

```
hlrlookup/
├── app.py              # Flask web app + JSON API
├── cli.py              # command-line bulk tool
├── playwright_lookup.py  # Excel → e164.com website → Excel (browser automation)
├── make_input_template.py # generate a starter input .xlsx
├── hlr/
│   ├── india.py        # MSISDN normalise/validate
│   ├── providers.py    # mock + real HTTP providers (pluggable)
│   └── engine.py       # concurrent bulk engine, rate limiting, CSV
├── templates/          # web UI
├── sample_numbers.csv  # 1000 demo numbers
└── test_hlr.py
```
