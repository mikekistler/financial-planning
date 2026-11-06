#!/usr/bin/env python3
"""Verify the data in a generated fund CSV.

Checks:
  1. When consecutive transactions are for the same fund, Shares Owned equals
     the previous transaction's Shares Owned plus this transaction's Quantity.
  2. For every transaction, Quantity equals Dollar Amount / Share Price,
     rounded to 3 decimal places.

Usage: verify_csv.py FILE.csv [FILE.csv ...]
Exits with status 1 if any problem is found.
"""
import csv
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

THREE_PLACES = Decimal("0.001")


def parse(value):
    value = (value or "").strip().replace(",", "").replace("$", "")
    if not value:
        return None
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def verify(path):
    errors = 0
    prev_owned = None
    prev_symbol = None
    with open(path, newline="") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            label = f"{path}:{lineno} ({row.get('Trade Date')} {row.get('Transaction Description')})"
            symbol = row.get("Fund Symbol")
            dollars = parse(row.get("Dollar Amount"))
            qty = parse(row.get("Quantity"))
            price = parse(row.get("Share Price"))
            owned = parse(row.get("Shares Owned"))

            if qty is None or owned is None:
                print(f"{label}: missing or invalid Quantity/Shares Owned")
                errors += 1
            elif prev_owned is not None and prev_symbol == symbol:
                expected = prev_owned + qty
                if expected != owned:
                    print(f"{label}: Shares Owned {owned} != previous {prev_owned} + Quantity {qty} = {expected}")
                    errors += 1

            if dollars is None or qty is None or price is None or price == 0:
                print(f"{label}: missing or invalid Dollar Amount/Quantity/Share Price")
                errors += 1
            else:
                expected = (dollars / price).quantize(THREE_PLACES, rounding=ROUND_HALF_UP)
                if expected != qty:
                    print(f"{label}: Quantity {qty} != Dollar Amount {dollars} / Share Price {price} = {expected}")
                    errors += 1

            if owned is not None:
                prev_owned = owned
            prev_symbol = symbol
    return errors


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    total = sum(verify(p) for p in argv)
    print(f"{total} problem(s) found" if total else "OK")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
