"""Extract fund transactions from OCR'd account statement PDFs into a CSV.

Usage:
    python extract.py statement.pdf [-o transactions.csv]

The default output name is the input name with ".pdf" (and "-scan.ocr") replaced by ".csv".
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import cast

import pymupdf

FUND_SYMBOLS = {
    "40": "VFINX",
    "52": "VGHCX",
    "81": "VWIGX",
    "98": "VEXMX",
}

FIELDS = [
    "Trade Date",
    "Fund Symbol",
    "Transaction Description",
    "Dollar Amount",
    "Quantity",
    "Share Price",
    "Commissions & Fees",
    "Shares Owned",
]

FUND_RE = re.compile(
    r"(?:Tele-?\s*Account\s*(?:No\.?|Number)|Fund\s*(?:No\.?|Number|#))\s*:?\s*(\d{1,3})\b",
    re.IGNORECASE,
)
# Statements from 2003 on: "Fund / Account no. 0098 / 09875995419"
FUND_ACCOUNT_RE = re.compile(
    r"Fund\s*/\s*Account\s*(?:No\.?|Number|#)\s*:?\s*(\d{1,4})\s*/\s*\d+",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}(?:[/-](?:\d{4}|\d{2}))?$")
YEAR_RE = re.compile(r"\b((?:19|20)\d\d)\s+CALENDAR\s+YEAR", re.IGNORECASE)
ROW_TOLERANCE = 4.0  # points
DATE_MAX_X = 80.0  # trade dates sit in the leftmost column
# Numbers such as 1,234.56  $50.00  (12.5)  -3.210  .5
NUM_RE = re.compile(r"^[-(]?\$?[-(]?\d[\d,]*(?:\.\d+)?\)?$|^[-(]?\$?\.\d+\)?$")
FEE_RE = re.compile(r"\b(?:FEE|FEES|COMMISSION|COMMISSIONS)\b", re.IGNORECASE)


def clean_number(token: str) -> str:
    negative = token.startswith("-") or "(" in token
    value = re.sub(r"[^\d.]", "", token)
    return f"-{value}" if negative else value


Word = tuple[float, float, float, float, str, int, int, int]


def page_lines(page: pymupdf.Page):
    """Yield lists of words grouped into visual rows by vertical position."""
    raw = cast(list[Word], page.get_text("words"))
    words = sorted(raw, key=lambda w: (w[1] + w[3]) / 2)
    line: list[Word] = []
    top = 0.0
    for w in words:
        yc = (w[1] + w[3]) / 2
        if line and yc - top > ROW_TOLERANCE:
            yield sorted(line, key=lambda x: x[0])
            line = []
        if not line:
            top = yc
        line.append(w)
    if line:
        yield sorted(line, key=lambda x: x[0])


def build_row(fund: str, date: str, tokens: list[str], page_number: int) -> dict[str, str] | None:
    desc: list[str] = []
    nums: list[str] = []
    for tok in tokens:
        # Numbers count as amounts only after the description has started.
        if NUM_RE.match(tok) and (desc or nums):
            nums.append(tok)
        else:
            desc.append(tok)

    # Only the last four numbers are amounts; earlier ones belong to the description.
    while len(nums) > 4:
        desc.append(nums.pop(0))

    if " ".join(desc).strip().lower() == "ending balance":
        return None

    row = {
        "Fund Symbol": FUND_SYMBOLS.get(fund, ""),
        "Trade Date": date,
        "Transaction Description": " ".join(desc),
        "Dollar Amount": "",
        "Commissions & Fees": "",
        "Quantity": "",
        "Share Price": "",
        "Shares Owned": "",
    }
    values = [clean_number(n) for n in nums]
    if len(values) == 4:
        (
            row["Dollar Amount"],
            row["Share Price"],
            row["Quantity"],
            row["Shares Owned"],
        ) = values
    elif len(values) == 1:
        row["Shares Owned"] = values[0]
    else:
        print(
            f"error: expected 1 or 4 amounts, found {len(nums)} for fund {fund} "
            f"on {date}, page {page_number} ({' '.join(desc)}): {' '.join(nums)}",
            file=sys.stderr,
        )
    return row


def fee_amount(tokens: list[str]) -> str | None:
    desc: list[str] = []
    nums: list[str] = []
    for tok in tokens:
        if NUM_RE.match(tok) and (desc or nums):
            nums.append(tok)
        else:
            desc.append(tok)

    if FEE_RE.search(" ".join(desc)) and len(nums) == 1:
        return clean_number(nums[0])
    return None


def extract(pdf_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    fund = ""
    year = ""

    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc.pages(), start=1):
            previous_transaction: dict[str, str] | None = None
            for words in page_lines(page):
                text = " ".join(w[4] for w in words)

                m = YEAR_RE.search(text)
                if m:
                    year = m.group(1)

                m = FUND_ACCOUNT_RE.search(text) or FUND_RE.search(text)
                if m:
                    fund = m.group(1).lstrip("0") or "0"
                    if fund not in FUND_SYMBOLS:
                        print(f"warning: unknown fund number {fund} in {pdf_path.name}", file=sys.stderr)
                    previous_transaction = None
                    continue

                fee = fee_amount([w[4] for w in words])
                if fee is not None:
                    if previous_transaction is not None:
                        previous_transaction["Commissions & Fees"] = fee
                    previous_transaction = None
                    continue

                first = words[0]
                if fund and first[0] < DATE_MAX_X and DATE_RE.match(first[4]):
                    date = first[4]
                    if date.count("/") + date.count("-") == 1 and year:
                        date = f"{date}/{year}"
                    row = build_row(fund, date, [w[4] for w in words[1:]], page_number)
                    if row:
                        rows.append(row)
                        previous_transaction = row
                        continue
                previous_transaction = None
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Statement PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output CSV file")
    args = parser.parse_args()

    output = args.output or args.pdf.with_name(args.pdf.stem.replace("-scan.ocr", "") + ".csv")

    rows = extract(args.pdf)
    print(f"{args.pdf}: {len(rows)} transactions", file=sys.stderr)

    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
