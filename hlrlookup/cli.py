#!/usr/bin/env python3
"""
Command-line bulk HLR lookup — no web server needed.

Examples:
    python cli.py numbers.txt                 # look up a file, print a summary
    python cli.py numbers.txt -o results.csv  # write full results to CSV
    python cli.py 9876543210 9123456780       # look up numbers given inline
    HLR_PROVIDER=http python cli.py numbers.txt   # use a real gateway

Reads numbers from files and/or inline args. Numbers are normalised and
de-duplicated. Uses the offline mock provider unless HLR_PROVIDER=http.
"""

import os
import sys
import argparse

from hlr.engine import BulkJob


def _read_inputs(items):
    raw = []
    for item in items:
        if os.path.isfile(item):
            with open(item, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    for part in line.replace("\r", "").split(","):
                        part = part.strip()
                        if part:
                            raw.append(part)
        else:
            raw.append(item)
    return raw


def main():
    ap = argparse.ArgumentParser(description="Bulk HLR lookup for Indian mobile numbers.")
    ap.add_argument("inputs", nargs="+", help="number(s) and/or file(s) of numbers")
    ap.add_argument("-o", "--output", help="write full results to this CSV file")
    ap.add_argument("-c", "--concurrency", type=int, default=10)
    ap.add_argument("-r", "--rate", type=float, default=8.0)
    args = ap.parse_args()

    raw = _read_inputs(args.inputs)
    if not raw:
        print("No numbers found.", file=sys.stderr)
        sys.exit(1)

    job = BulkJob(raw, concurrency=args.concurrency, rate_per_sec=args.rate)
    print(f"Provider: {job.provider_name}  |  input: {job.total_input}  "
          f"unique: {job.total}  duplicates: {job.duplicates}  invalid: {len(job.invalid)}")
    if job.total == 0:
        print("Nothing valid to look up.", file=sys.stderr)
        sys.exit(1)

    job.run()  # blocking

    summ = job.summary()
    print("\n=== Summary ===")
    for status, n in sorted(summ["by_status"].items()):
        print(f"  {status:<10} {n}")
    print(f"  ported     {summ['ported']}")
    if summ["by_operator"]:
        print("  operators:")
        for op, n in sorted(summ["by_operator"].items(), key=lambda x: -x[1]):
            print(f"    {op:<24} {n}")

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(job.to_csv())
        print(f"\nWrote {len(job.results)} results to {args.output}")


if __name__ == "__main__":
    main()
