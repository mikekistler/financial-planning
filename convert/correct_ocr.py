#!/usr/bin/env python3
"""Fix OCR text in a PDF: replace the text layer's current text on one page with the desired text."""

import argparse
import os
import sys
from pathlib import Path

import pymupdf


def find_lines(page: pymupdf.Page, old: str) -> list[dict]:
    """Return text-layer lines containing `old`, each with its joined text and spans."""
    found = []
    for block in page.get_textpage().extractDICT()["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"])
            if old in text:
                found.append({"text": text, "spans": line["spans"], "bbox": pymupdf.Rect(line["bbox"])})
    return found


def replace_line(page: pymupdf.Page, line: dict, old: str, new: str) -> str:
    first = line["spans"][0]
    updated = line["text"].replace(old, new)
    # Shrink vertically so the redaction doesn't clip neighbouring lines.
    box = line["bbox"]
    shrink = box.height * 0.2
    page.add_redact_annot(pymupdf.Rect(box.x0, box.y0 + shrink, box.x1, box.y1 - shrink))
    page.apply_redactions(images=0, graphics=0)  # 0 = keep the scanned image
    page.insert_text(first["origin"], updated, fontsize=first["size"], render_mode=3)  # invisible
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="PDF whose text layer should be corrected")
    ap.add_argument("page", type=int, help="1-based page number")
    ap.add_argument("old", help="current OCR text (may be part of a line)")
    ap.add_argument("new", help="desired text")
    ap.add_argument("-o", "--output", type=Path, help="write here instead of overwriting the input")
    args = ap.parse_args()

    if not args.old:
        ap.error("current OCR text must not be empty")

    doc = pymupdf.open(args.input)
    if not 1 <= args.page <= len(doc):
        print(f"Page {args.page} is out of range (1-{len(doc)})", file=sys.stderr)
        return 1
    page = doc[args.page - 1]

    lines = find_lines(page, args.old)
    if not lines:
        print(f"Text {args.old!r} not found on page {args.page}", file=sys.stderr)
        return 1

    for line in lines:
        print(f"{line['text']!r} -> {replace_line(page, line, args.old, args.new)!r}", file=sys.stderr)

    output = args.output or args.input
    # The input is open, so save beside it and swap in the result.
    tmp = output.with_name(output.name + ".tmp")
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, output)
    print(f"Wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
