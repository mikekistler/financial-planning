# PDF re-OCR with Qwen2.5-VL

Qwen 2.5 itself is text-only. Its vision variant, **Qwen2.5-VL**, does the OCR.
This tool renders each page, sends it to a local Ollama model, removes the existing
text layer, and adds the new text as an invisible layer (searchable/selectable).
Line positions are approximate: lines are spread evenly down the page.

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

Options: `--model`, `--host`, `--dpi`, `--max-side`, `--num-ctx`.

## Notes

- Always spot-check numbers; vision LLMs can misread digits.
- The 32B model was too slow on a 32 GB Mac, so 7B is the default.
