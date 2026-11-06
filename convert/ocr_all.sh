#!/usr/bin/env bash
set -euo pipefail

SCAN_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

shopt -s nullglob
for pdf in "$SCAN_DIR"/*-scan.pdf; do
    echo "=== $pdf ==="
    uv run --project "$SCRIPT_DIR" "$SCRIPT_DIR/ocr_pdf.py" "$pdf"
done
