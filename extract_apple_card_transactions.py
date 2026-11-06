#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pypdf"]
# ///
"""Extract transactions from Apple Card statement PDFs into a CSV for Numbers.

Usage: extract_apple_card_transactions.py [-o out.csv] statement1.pdf [statement2.pdf ...]

Payments and purchases are both included (Type column); Daily Cash is omitted.
Output is sorted by date.
"""
import argparse
import csv
import re
import sys
from datetime import datetime
from decimal import Decimal

from pypdf import PdfReader

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
AMOUNT_RE = re.compile(r"^(-?)\$([\d,]+\.\d{2})$")
PCT_RE = re.compile(r"^\d+(\.\d+)?%$")


def parse_amount(s):
    m = AMOUNT_RE.match(s)
    value = Decimal(m.group(2).replace(",", ""))
    return -value if m.group(1) else value


def parse_statement(path):
    lines = []
    for page in PdfReader(path).pages:
        lines.extend(l.strip() for l in (page.extract_text() or "").splitlines())

    rows, totals = [], {}
    section = current = pending_total = None
    skip = {"Date", "Description", "Daily Cash", "Amount"}

    def flush():
        nonlocal current
        if current:
            parts = current["lines"]
            if section == "Payments":
                amount = parse_amount(parts.pop())
            else:
                # Description runs until the Daily Cash % or (for returns) the
                # Amount. Normal rows: % , Daily Cash $, Amount, then optional
                # extra Daily Cash lines which are ignored.
                i = next(i for i, l in enumerate(parts)
                         if PCT_RE.match(l) or AMOUNT_RE.match(l))
                amount = parse_amount(parts[i] if AMOUNT_RE.match(parts[i]) else parts[i + 2])
                if AMOUNT_RE.match(parts[i]) and len(parts) >= i + 4:
                    # Return: a trailing "Daily Cash Adjustment" is charged
                    # back as its own amount.
                    rows.append((current["date"], parts[i + 1], section,
                                 parse_amount(parts[i + 3])))
                parts = parts[:i]
            rows.append((current["date"], " ".join(parts), section, amount))
        current = None

    for line in lines:
        if not line:
            continue
        if line in ("Payments", "Transactions"):
            flush()
            section = line
        elif line.startswith("Total payments for this period"):
            flush()
            pending_total = "Payments"
        elif line.startswith("Total charges, credits and returns"):
            flush()
            pending_total = "Transactions"
        elif line.startswith("Total Daily Cash"):
            flush()
        elif pending_total and AMOUNT_RE.match(line):
            totals[pending_total] = parse_amount(line)
            pending_total = None
        elif section and DATE_RE.match(line):
            flush()
            current = {"date": line, "lines": []}
        elif current is not None and line not in skip:
            current["lines"].append(line)
            if section == "Payments" and AMOUNT_RE.match(line):
                flush()
    flush()
    return rows, totals


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", help="Apple Card statement PDFs")
    ap.add_argument("-o", "--output", default="apple_card_transactions.csv")
    args = ap.parse_args()

    out = []
    for path in args.files:
        rows, totals = parse_statement(path)
        got = sum(r[3] for r in rows if r[2] == "Transactions")
        exp = totals.get("Transactions")
        if isinstance(exp, Decimal) and got != exp:
            print(f"warning: {path}: transactions total {got} != statement {exp}",
                  file=sys.stderr)
        out.extend(rows)

    out.sort(key=lambda r: datetime.strptime(r[0], "%m/%d/%Y"))
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Description", "Type", "Amount"])
        for date, desc, section, amount in out:
            w.writerow([date, desc, section.rstrip("s"), f"{amount:.2f}"])
    print(f"Wrote {len(out)} rows to {args.output}")


if __name__ == "__main__":
    main()
