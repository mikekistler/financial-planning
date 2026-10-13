# PDF re-OCR (macOS Vision + Qwen2.5-VL)

Each page is OCR'd with the macOS Vision framework, which gives fast text with exact
line positions. Lines Vision is unsure about (low confidence, odd characters, very long
words) are cropped and re-read by a local Qwen2.5-VL model via Ollama. The existing text
layer is removed and replaced with the result as an invisible layer (searchable/selectable).

## Setup

```sh
brew install ollama
ollama pull qwen2.5vl:7b   # ~6 GB
uv sync
```

## Usage

```sh
uv run ocr_pdf.py statement.pdf                      # writes statement.ocr.pdf
uv run ocr_pdf.py statement.pdf -o out.pdf
```

Options: `--model`, `--host`, `--dpi`, `--threshold`, `--no-refine`.

## Notes

- Always spot-check numbers; both Vision and the model can misread digits.
- Each replaced line is printed to stderr so you can review the changes.
- The 32B model was too slow on a 32 GB Mac, so 7B is the default.
- Requires macOS (uses the Vision framework).
