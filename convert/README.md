# PDF re-OCR with Qwen2.5-VL

Qwen 2.5 32B itself is text-only. Its vision variant, **Qwen2.5-VL 32B**, does the OCR.
This tool renders each page, sends it to a local Ollama model, removes the existing
text layer, and adds the new text as an invisible, positioned layer (searchable/selectable).

## Setup

```sh
brew install ollama
ollama pull qwen2.5vl:32b   # ~21 GB; needs roughly 32 GB+ RAM
uv sync
```

## Usage

```sh
python ocr_pdf.py statement.pdf                      # writes statement.ocr.pdf
uv run ocr_pdf.py statement.pdf                      # writes statement.ocr.pdf
uv ru

Options: `--model`, `--host`, `--dpi`, `--max-side`.

## Notes

- Always spot-check numbers; vision LLMs can misread digits.
- If the model returns no bounding boxes for a page, the text is added at page level only.
- If memory is tight, try `--model qwen2.5vl:7b`.
