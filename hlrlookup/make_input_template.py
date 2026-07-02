#!/usr/bin/env python3
"""
Make a starter Excel file for playwright_lookup.py.

    python make_input_template.py                 # -> numbers_template.xlsx (few rows)
    python make_input_template.py -o mine.xlsx --sample 1000

Put your real numbers in the "mobile_number" column (one per row) and feed the
file to:  python playwright_lookup.py -i mine.xlsx -o results.xlsx --headed
"""

import argparse
from openpyxl import Workbook


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="numbers_template.xlsx")
    ap.add_argument("--sample", type=int, default=0,
                    help="fill with N generated sample numbers instead of blanks")
    args = ap.parse_args()

    wb = Workbook()
    ws = wb.active
    ws.title = "numbers"
    ws.append(["mobile_number"])

    if args.sample:
        for i in range(args.sample):
            first = "6789"[i % 4]
            rest = str(100000000 + (i * 998237) % 899999999)[:9]
            ws.append([first + rest])
    else:
        for ex in ["9876543210", "+91 91234 56789", "09123456780"]:
            ws.append([ex])

    wb.save(args.output)
    print(f"Wrote {args.output}  (column: mobile_number)")


if __name__ == "__main__":
    main()
