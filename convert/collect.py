"""Collect all transactions for one fund symbol from the .csv/.xlsx files in a folder.

Usage:
    python collect.py VFINX [folder] [-o VFINX.csv] [--recursive]

The output is a CSV (or .xlsx if -o ends in .xlsx), sorted by trade date, with a
"Source File" column showing where each row came from. Both formats open in Numbers.
"""

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

SYMBOL_HEADERS = ("fund symbol", "symbol")
DATE_HEADERS = ("trade date", "date", "transaction date", "settlement date")
DATE_FORMATS = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%y")


def read_csv(path: Path) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open(newline="", encoding=encoding) as f:
                return [row for row in csv.reader(f)]
        except UnicodeDecodeError:
            continue
    return []


def format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%Y")
    if isinstance(value, date):
        return value.strftime("%m/%d/%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_xlsx(path: Path) -> list[tuple[str, list[list[str]]]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        return [
            (ws.title, [[format_cell(c) for c in row] for row in ws.iter_rows(values_only=True)])
            for ws in wb.worksheets
        ]
    finally:
        wb.close()


def find_header(rows: list[list[str]]) -> int | None:
    """Index of the first row that contains a symbol column header."""
    for i, row in enumerate(rows):
        if any(c.strip().lower() in SYMBOL_HEADERS for c in row):
            return i
    return None


def extract(rows: list[list[str]], symbol: str, source: str) -> tuple[list[str], list[dict[str, str]]]:
    start = find_header(rows)
    if start is None:
        return [], []
    header = [c.strip() for c in rows[start]]
    sym_col = next(i for i, h in enumerate(header) if h.lower() in SYMBOL_HEADERS)
    out = []
    for row in rows[start + 1 :]:
        if len(row) <= sym_col or row[sym_col].strip().upper() != symbol:
            continue
        rec = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(header) if h}
        rec["Source File"] = source
        out.append(rec)
    return [h for h in header if h], out


def parse_date(value: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return date.max  # unparseable dates sort last


def to_number(value: str) -> float | str:
    """Convert numeric-looking text so Numbers treats it as a number in xlsx output."""
    text = value.replace(",", "").replace("$", "")
    if re.fullmatch(r"\(?-?\d+(\.\d+)?\)?", text):
        try:
            return -float(text.strip("()")) if text.startswith("(") else float(text)
        except ValueError:
            pass
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help="Fund symbol, e.g. VFINX")
    parser.add_argument("folder", nargs="?", type=Path, default=Path("."), help="Folder to scan (default: .)")
    parser.add_argument("-o", "--output", type=Path, help="Output file (default: <SYMBOL>.csv)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Also scan subfolders")
    args = parser.parse_args()

    symbol = args.symbol.strip().upper()
    output = args.output or Path(f"{symbol}.csv")
    pattern = "**/*" if args.recursive else "*"
    files = sorted(
        p
        for p in args.folder.glob(pattern)
        if p.suffix.lower() in (".csv", ".xlsx")
        and not p.name.startswith(("~$", "."))
        and p.resolve() != output.resolve()
        and p.stem.upper() != symbol  # earlier output, e.g. VFINX.csv
    )

    columns: list[str] = []
    records: list[dict[str, str]] = []
    for path in files:
        try:
            if path.suffix.lower() == ".csv":
                sheets = [("", read_csv(path))]
            else:
                sheets = read_xlsx(path)
        except Exception as e:
            print(f"warning: could not read {path.name}: {e}", file=sys.stderr)
            continue
        found = 0
        for title, rows in sheets:
            source = f"{path.name} [{title}]" if len(sheets) > 1 else path.name
            header, recs = extract(rows, symbol, source)
            for h in header:
                if h not in columns:
                    columns.append(h)
            records.extend(recs)
            found += len(recs)
        print(f"{path.name}: {found} rows", file=sys.stderr)

    if not records:
        sys.exit(f"No transactions for {symbol} found in {len(files)} file(s) under {args.folder}")

    date_col = next((c for c in columns if c.lower() in DATE_HEADERS), None)
    if date_col:
        records.sort(key=lambda r: parse_date(r.get(date_col, "")))
    columns.append("Source File")

    if output.suffix.lower() == ".xlsx":
        wb = Workbook()
        ws = wb.active
        if ws is None:
            raise RuntimeError("Workbook has no active worksheet")
        ws.append(columns)
        for r in records:
            ws.append([r.get(c, "") if c in ("Source File", date_col) else to_number(r.get(c, "")) for c in columns])
        wb.save(output)
    else:
        with output.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns, restval="")
            w.writeheader()
            w.writerows(records)

    print(f"Wrote {len(records)} transactions for {symbol} to {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
