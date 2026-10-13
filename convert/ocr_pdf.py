#!/usr/bin/env python3
"""Re-OCR scanned PDFs with a local Qwen2.5-VL model (via Ollama) and replace the text layer."""

import argparse
import sys
from pathlib import Path

import pymupdf
import ollama

PROMPT = (
    "Transcribe all text in this scanned financial statement exactly as written, "
    "top to bottom, one line of text per output line. Preserve numbers, dates, and "
    "punctuation. Output only the text."
)


def render_page(page: pymupdf.Page, dpi: int, max_side: int) -> bytes:
    """Render a page to PNG, downscaled so the longest side is <= max_side."""
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    longest = max(pix.width, pix.height)
    if longest > max_side:
        scale = max_side / longest
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom * scale, zoom * scale))
    return pix.tobytes("png")


def clear_text_layer(page: pymupdf.Page) -> None:
    """Remove existing (bad) OCR text while keeping the scanned image."""
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=0, graphics=0)  # 0 = keep images


def add_invisible_text(page: pymupdf.Page, text: str) -> None:
    """Add invisible text lines spread evenly down the page (positions are approximate)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return
    margin = 36
    step = (page.rect.height - 2 * margin) / len(lines)
    for n, line in enumerate(lines):
        page.insert_text(
            (margin, margin + (n + 1) * step),
            line,
            fontsize=min(step * 0.8, 10),
            render_mode=3,  # invisible
        )


def ocr_page(client: ollama.Client, model: str, image: bytes, num_ctx: int) -> str:
    parts: list[str] = []
    stream = client.chat(
        model=model,
        messages=[{"role": "user", "content": PROMPT, "images": [image]}],
        options={"temperature": 0, "num_ctx": num_ctx, "num_predict": 4096},
        stream=True,
    )
    for chunk in stream:
        parts.append(chunk["message"]["content"])
        print(f"\r  generated {len(parts)} tokens", end="", file=sys.stderr, flush=True)
        if chunk.get("done"):
            ns = 1e9
            print(
                f"\n  load {chunk['load_duration'] / ns:.1f}s, "
                f"prompt {chunk['prompt_eval_count']} tok in {chunk['prompt_eval_duration'] / ns:.1f}s, "
                f"output {chunk['eval_count']} tok in {chunk['eval_duration'] / ns:.1f}s",
                file=sys.stderr,
            )
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="input PDF")
    ap.add_argument("-o", "--output", type=Path, help="output PDF (default: <input>.ocr.pdf)")
    ap.add_argument("--model", default="qwen2.5vl:7b")
    ap.add_argument("--host", default=None, help="Ollama host (default: local)")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-side", type=int, default=1280, help="max image side sent to the model")
    ap.add_argument("--num-ctx", type=int, default=8192, help="context size; smaller uses less memory")
    args = ap.parse_args()

    output = args.output or args.input.with_suffix(".ocr.pdf")
    client = ollama.Client(host=args.host)
    doc = pymupdf.open(args.input)

    for i, page in enumerate(doc.pages(), 1):
        print(f"Page {i}/{len(doc)}...", file=sys.stderr)
        image = render_page(page, args.dpi, args.max_side)
        text = ocr_page(client, args.model, image, args.num_ctx)

        clear_text_layer(page)
        add_invisible_text(page, text)

    doc.save(output, garbage=3, deflate=True)
    print(f"Wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
