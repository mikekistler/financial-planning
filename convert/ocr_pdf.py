#!/usr/bin/env python3
"""Re-OCR scanned PDFs with a local Qwen2.5-VL model (via Ollama) and replace the text layer."""

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf
import ollama

PROMPT = (
    "Transcribe all text in this scanned financial statement exactly as written, "
    "preserving numbers, dates, and punctuation. Return only a JSON array with one "
    'object per line of text: {"text": "...", "bbox": [x1, y1, x2, y2]} where bbox '
    "is in pixel coordinates of this image."
)


def render_page(page: pymupdf.Page, dpi: int, max_side: int) -> tuple[bytes, int, int]:
    """Render a page to PNG, downscaled so the longest side is <= max_side."""
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    longest = max(pix.width, pix.height)
    if longest > max_side:
        scale = max_side / longest
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom * scale, zoom * scale))
    return pix.tobytes("png"), pix.width, pix.height


def parse_lines(raw: str) -> list[dict] | None:
    """Extract the JSON array from the model reply; None if unparseable."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return [
        d for d in data
        if isinstance(d, dict) and isinstance(d.get("text"), str)
    ]


def clear_text_layer(page: pymupdf.Page) -> None:
    """Remove existing (bad) OCR text while keeping the scanned image."""
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=0, graphics=0)  # 0 = keep images


def add_invisible_text(page: pymupdf.Page, lines: list[dict], img_w: int, img_h: int) -> None:
    sx = page.rect.width / img_w
    sy = page.rect.height / img_h
    for line in lines:
        text = line["text"].strip()
        bbox = line.get("bbox")
        if not text:
            continue
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        x1, y1, x2, y2 = (float(v) for v in bbox)
        height = max((y2 - y1) * sy, 1)
        # Baseline sits near the bottom of the box.
        page.insert_text(
            (x1 * sx, y2 * sy - height * 0.2),
            text,
            fontsize=height * 0.8,
            render_mode=3,  # invisible
        )


def add_page_level_text(page: pymupdf.Page, raw: str) -> None:
    """Fallback when no bounding boxes are available: invisible text at top-left."""
    page.insert_textbox(page.rect, raw, fontsize=8, render_mode=3)


def ocr_page(client: ollama.Client, model: str, image: bytes) -> str:
    resp = client.chat(
        model=model,
        messages=[{"role": "user", "content": PROMPT, "images": [image]}],
        options={"temperature": 0},
    )
    return resp["message"]["content"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="input PDF")
    ap.add_argument("-o", "--output", type=Path, help="output PDF (default: <input>.ocr.pdf)")
    ap.add_argument("--model", default="qwen2.5vl:32b")
    ap.add_argument("--host", default=None, help="Ollama host (default: local)")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-side", type=int, default=1792, help="max image side sent to the model")
    ap.add_argument("--text-out", type=Path, help="also write the plain text to this file")
    args = ap.parse_args()

    output = args.output or args.input.with_suffix(".ocr.pdf")
    client = ollama.Client(host=args.host)
    doc = pymupdf.open(args.input)
    all_text: list[str] = []

    for i, page in enumerate(doc.pages(), 1):
        print(f"Page {i}/{len(doc)}...", file=sys.stderr)
        image, w, h = render_page(page, args.dpi, args.max_side)
        raw = ocr_page(client, args.model, image)
        lines = parse_lines(raw)

        clear_text_layer(page)
        if lines:
            add_invisible_text(page, lines, w, h)
            all_text.append("\n".join(l["text"] for l in lines))
        else:
            print(f"  page {i}: no bounding boxes returned, using page-level text", file=sys.stderr)
            add_page_level_text(page, raw)
            all_text.append(raw)

    doc.save(output, garbage=3, deflate=True)
    if args.text_out:
        args.text_out.write_text("\n\n".join(all_text), encoding="utf-8")
    print(f"Wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
