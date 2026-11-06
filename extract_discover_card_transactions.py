#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pypdf"]
# ///
"""Extract transactions from Discover Card statement PDFs into a CSV for Numbers.

Usage: extract_discover_card_transactions.py [-o out.csv] statement1.pdf [statement2.pdf ...]

Payments/credits and purchases are both included (Type column), along with the
merchant category. Output is sorted by date. Purchases are positive and
payments/credits are negative, as on the statement.
"""
import argparse
import csv
import re
import sys
from datetime import date
from decimal import Decimal

from pypdf import PdfReader

PERIOD_RE = re.compile(r"OPEN TO CLOSE DATE:\s*(\d\d)/(\d\d)/(\d{4})\s*-\s*(\d\d)/(\d\d)/(\d{4})")
# The Cashback Bonus sidebar text can be glued onto the front of a row.
SIDEBAR_RE = re.compile(r"^.*?Cashback Bonus \+\$[\d,]+\.\d\d(?=\d\d/\d\d )")
ROW_RE = re.compile(r"^(\d\d)/(\d\d) (.*)$")
AMOUNT_END_RE = re.compile(r"^(.*?)\s*(-?)\$([\d,]+\.\d{2})$")
SUMMARY_RE = re.compile(r"^(Payments and Credits|Purchases)\s+([+-]?)\$([\d,]+\.\d{2})$", re.I)
CATEGORIES = [
    "Merchandise", "Home Improvement", "Services", "Restaurants", "Supermarkets",
    "Gasoline", "Travel/Entertainment", "Medical Services", "Department Stores",
    "Warehouse Clubs", "Automotive", "Education", "Utilities", "Other",
]
CATEGORY_RE = re.compile(r"^(.*?)\s*\b(" + "|".join(map(re.escape, CATEGORIES)) + r")$")
END_MARKERS = ("PREVIOUS BALANCE", "TOTAL FEES FOR THIS PERIOD", "TOTAL INTEREST FOR THIS PERIOD")


def parse_statement(path):
    lines = []
    for page in PdfReader(path).pages:
        lines.extend(l.strip() for l in (page.extract_text() or "").splitlines())

    period = next((PERIOD_RE.search(l) for l in lines if PERIOD_RE.search(l)), None)
    if not period:
        raise ValueError("statement period not found")
    open_year, close_month, close_year = int(period[3]), int(period[4]), int(period[6])

    def year_for(month):
        # Statements span at most ~1 month, so a month after the close month
        # belongs to the opening year.
        return open_year if month > close_month else close_year

    rows, totals = [], {}
    current = None
    in_credits = False  # last row was in the Payments and Credits table

    def finish(parts, amount, sign):
        nonlocal current
        month, day = current["month"], current["day"]
        desc_lines = current["lines"] + ([parts[0]] if parts[0] else [])
        category = ""
        m = CATEGORY_RE.match(parts[0]) if parts[0] else None
        if m:
            desc_lines = current["lines"] + ([m.group(1)] if m.group(1) else [])
            category = m.group(2)
        value = Decimal(amount.replace(",", ""))
        if sign:
            value = -value
        rows.append((date(year_for(month), month, day),
                     " ".join(desc_lines), "Payment" if value < 0 else "Purchase",
                     category, value))
        current = None

    for line in lines:
        line = SIDEBAR_RE.sub("", line)
        if not line:
            continue
        sm = SUMMARY_RE.match(line)
        if sm:
            totals[sm.group(1).upper()] = Decimal(sm.group(3).replace(",", "")) * (-1 if sm.group(2) == "-" else 1)
            continue
        if line.startswith(END_MARKERS):
            current = None
            continue
        rm = ROW_RE.match(line)
        if rm:
            current = {"month": int(rm.group(1)), "day": int(rm.group(2)), "lines": []}
            rest = rm.group(3)
            am = AMOUNT_END_RE.match(rest)
            if am:
                finish((am.group(1),), am.group(3), am.group(2))
            else:
                current["lines"].append(rest)
        elif current is not None:
            am = AMOUNT_END_RE.match(line)
            if am:
                finish((am.group(1),), am.group(3), am.group(2))
            elif not line.startswith(("SEE DETAILS", "Continued on")):
                current["lines"].append(line)
    return rows, totals


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", help="Discover Card statement PDFs")
    ap.add_argument("-o", "--output", default="discover_card_transactions.csv")
    args = ap.parse_args()

    out = []
    for path in args.files:
        rows, totals = parse_statement(path)
        for kind, label in (("PURCHASES", "Purchase"), ("PAYMENTS AND CREDITS", "Payment")):
            got = sum(r[4] for r in rows if r[2] == label)
            exp = totals.get(kind)
            if exp is not None and got != exp:
                print(f"warning: {path}: {kind.lower()} total {got} != statement {exp}",
                      file=sys.stderr)
        out.extend(rows)

    out.sort(key=lambda r: r[0])
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Description", "Type", "Category", "Amount"])
        for d, desc, kind, cat, amount in out:
            w.writerow([d.strftime("%m/%d/%Y"), desc, kind, cat, f"{amount:.2f}"])
    print(f"Wrote {len(out)} rows to {args.output}")


if __name__ == "__main__":
    main()
