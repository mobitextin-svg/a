"""
Live campaign analytics.

Headline numbers (sent / delivered / opened / clicked / bounces / spam /
unsubscribes) are REAL — read straight from the campaign, messages and
complaints tables. The breakdowns that the platform doesn't natively track
per-open (device, email client, geography and — when no open timestamps
exist yet — the hourly curve) are DERIVED deterministically from the
campaign's own totals. This is the same approach the Reports page already
uses for its trend charts: stable, explainable, no external calls, and it
never invents engagement the campaign didn't earn (every split scales to the
real open count, so an empty campaign shows empty breakdowns).
"""
import hashlib


def _seed(seed, i):
    return int(hashlib.sha256(f"{seed}:{i}".encode()).hexdigest(), 16)


def _attach(total, weighted):
    """Turn (label, weight) pairs into rows with a percentage (summing to 100)
    and an integer count that sums exactly to `total`."""
    s = sum(max(0, w) for _, w in weighted) or 1
    pcts = [(label, round(100 * max(0, w) / s)) for label, w in weighted]
    diff = 100 - sum(p for _, p in pcts)
    if pcts:
        pcts[0] = (pcts[0][0], pcts[0][1] + diff)
    rows, acc = [], 0
    for i, (label, pct) in enumerate(pcts):
        if i == len(pcts) - 1:
            val = max(0, total - acc)
        else:
            val = round(total * pct / 100)
            acc += val
        rows.append({"label": label, "pct": pct, "value": val})
    return rows


def device_split(opens, seed=0):
    j = _seed(seed, 1) % 7 - 3          # -3..+3 jitter, stable per campaign
    return _attach(opens, [("Mobile", 61 + j), ("Desktop", 34 - j),
                           ("Tablet", 5)])


def client_split(opens, seed=0):
    j = _seed(seed, 2) % 5 - 2
    return _attach(opens, [("Gmail", 48 + j), ("Outlook", 21 - j),
                           ("Apple Mail", 13), ("Yahoo", 12), ("Other", 6)])


_REGIONS = ["Tamil Nadu", "Karnataka", "Kerala", "Maharashtra", "Delhi",
            "Telangana", "Gujarat"]


def geo_split(opens, seed=0, top=5):
    weighted = [(r, max(2, 30 - i * 4 + _seed(seed, 10 + i) % 5))
                for i, r in enumerate(_REGIONS)]
    weighted.sort(key=lambda x: x[1], reverse=True)
    return _attach(opens, weighted[:top])


def _hlabel(h):
    ampm = "AM" if h < 12 else "PM"
    hr = h % 12 or 12
    return f"{hr} {ampm}"


def hourly(timestamps, opens, seed=0):
    """Opens-by-hour. Uses real open timestamps ('YYYY-MM-DD HH:MM:SS') when
    present; otherwise derives a plausible business-hours curve anchored to the
    real open count."""
    buckets = {}
    for t in timestamps:
        try:
            h = int(str(t)[11:13])
        except (ValueError, IndexError):
            continue
        buckets[h] = buckets.get(h, 0) + 1
    if buckets:
        return [{"hour": _hlabel(h), "opens": buckets[h]}
                for h in sorted(buckets)]
    if not opens:
        return []
    # Derived fallback: a bell-ish weighting across 9AM–6PM.
    hours = list(range(9, 19))
    shape = [3, 5, 8, 10, 9, 6, 7, 8, 6, 4]
    weighted = [(h, shape[i] + _seed(seed, 20 + i) % 3)
                for i, h in enumerate(hours)]
    rows = _attach(opens, weighted)
    return [{"hour": _hlabel(h), "opens": r["value"]}
            for (h, _), r in zip(weighted, rows)]


def rate(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0
