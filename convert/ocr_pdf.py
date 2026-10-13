#!/usr/bin/env python3
# pyright: reportAttributeAccessIssue=false
# PyObjC exposes its symbols dynamically, which the type checker can't see.
"""Re-OCR scanned PDFs with macOS Vision, then re-read low-confidence lines with Qwen2.5-VL."""

import argparse
import sys
from pathlib import Path

import ollama
import pymupdf
import Vision
from Foundation import NSData

LINE_PROMPT = (
    "Transcribe the text in this image exactly as written. It is a single line from a "
    "financial statement. Output only the text."
)

Box = tuple[float, float, float, float]


def render_page(page: pymupdf.Page, dpi: int) -> bytes:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72))
    return pix.tobytes("png")


def clear_text_layer(page: pymupdf.Page) -> None:
    """Remove existing (bad) OCR text while keeping the scanned image."""
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=0, graphics=0)  # 0 = keep images


def recognize(png: bytes) -> list[tuple[str, Box, float]]:
    """Return (text, (x, y, w, h), confidence) per line; boxes are normalized, bottom-left origin."""
    data = NSData.dataWithBytes_length_(png, len(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    ok, err = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision request failed: {err}")
    results = []
    for obs in request.results():
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue
        box = obs.boundingBox()
        results.append((
            candidates[0].string(),
            (box.origin.x, box.origin.y, box.size.width, box.size.height),
            candidates[0].confidence(),
        ))
    return results


def is_suspect(text: str, confidence: float, threshold: float) -> bool:
    return (
        confidence < threshold
        or any(ord(c) > 126 for c in text)
        or any(len(tok) > 20 for tok in text.split())  # likely missing spaces
    )


def refine(client: ollama.Client, model: str, page: pymupdf.Page, box: Box, dpi: int) -> str | None:
    """Re-read one line from a crop of the page; None if the reply looks unusable."""
    W, H = page.rect.width, page.rect.height
    x, y, w, h = box
    pad = h * H * 0.3
    clip = pymupdf.Rect(x * W - pad, (1 - y - h) * H - pad, (x + w) * W + pad, (1 - y) * H + pad)
    png = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=clip & page.rect).tobytes("png")
    resp = client.chat(
        model=model,
        messages=[{"role": "user", "content": LINE_PROMPT, "images": [png]}],
        options={"temperature": 0, "num_ctx": 2048, "num_predict": 200},
    )
    text = resp["message"]["content"].strip()
    return text if text and "\n" not in text else None


def add_invisible_text(page: pymupdf.Page, lines) -> None:
    W, H = page.rect.width, page.rect.height
    for text, (x, y, _w, h), *_ in lines:
        height = h * H
        page.insert_text(
            (x * W, (1 - y) * H - height * 0.2),  # Vision origin is bottom-left
            text,
            fontsize=max(height * 0.8, 1),
            render_mode=3,  # invisible
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="default: <input>.ocr.pdf")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--model", default="qwen2.5vl:7b")
    ap.add_argument("--host", default=None, help="Ollama host (default: local)")
    ap.add_argument("--threshold", type=float, default=0.9, help="re-read lines below this confidence")
    ap.add_argument("--no-refine", action="store_true", help="Vision only; skip the model")
    args = ap.parse_args()

    output = args.output or args.input.with_suffix(".ocr.pdf")
    client = ollama.Client(host=args.host)
    doc = pymupdf.open(args.input)
    for i, page in enumerate(doc.pages(), 1):
        print(f"Page {i}/{len(doc)}...", file=sys.stderr)
        png = render_page(page, args.dpi)
        lines = recognize(png)
        if not args.no_refine:
            suspects = [n for n, (t, _, c) in enumerate(lines) if is_suspect(t, c, args.threshold)]
            print(f"  {len(suspects)}/{len(lines)} lines to re-read", file=sys.stderr)
            for n in suspects:
                text, box, conf = lines[n]
                new = refine(client, args.model, page, box, args.dpi)
                if new is not None:
                    print(f"  {conf:.2f} {text!r} -> {new!r}", file=sys.stderr)
                    lines[n] = (new, box, conf)
        clear_text_layer(page)
        add_invisible_text(page, lines)
    doc.save(output, garbage=3, deflate=True)
    print(f"Wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
