"""Print the OCR text from a PDF.

Usage:
    python dump_ocr.py statement.pdf [-p PAGE]
"""

import argparse
from pathlib import Path

import pymupdf


def dump_ocr(pdf_path: Path, only_page: int | None = None) -> None:
    with pymupdf.open(pdf_path) as doc:
        if only_page is not None and not 1 <= only_page <= len(doc):
            raise SystemExit(f"error: page {only_page} is out of range (1-{len(doc)})")
        for page_number, page in enumerate(doc.pages(), start=1):
            if only_page is not None and page_number != only_page:
                continue
            print(f"--- page {page_number} ---")
            text = str(page.get_text("text", sort=True))
            print(text.rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument("-p", "--page", type=int, help="1-based page number to dump (default: all pages)")
    args = parser.parse_args()

    dump_ocr(args.pdf, args.page)


if __name__ == "__main__":
    main()
