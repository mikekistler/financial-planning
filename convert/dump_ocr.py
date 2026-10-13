"""Print the OCR text from a PDF.

Usage:
    python dump_ocr.py statement.pdf
"""

import argparse
from pathlib import Path

import pymupdf


def dump_ocr(pdf_path: Path) -> None:
    with pymupdf.open(pdf_path) as doc:
        for page_number, page in enumerate(doc.pages(), start=1):
            print(f"--- page {page_number} ---")
            text = str(page.get_text("text", sort=True))
            print(text.rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    args = parser.parse_args()

    dump_ocr(args.pdf)


if __name__ == "__main__":
    main()
