# financial-planning

Resources for financial planning

## Run the notebook

This project uses [uv](https://docs.astral.sh/uv/) to manage its Python environment. It requires Python 3.14 or later.

### Set up the environment

From the project directory, create the virtual environment and install the notebook dependencies:

```bash
uv venv --python 3.14
source .venv/bin/activate
uv pip install matplotlib jupyter
```

### Open the notebook

You can run the notebook entirely inside VS Code:

1. Install the Microsoft **Python** and **Jupyter** extensions.
2. Open the `financial-planning` project folder in VS Code.
3. Open `irmaa-analysis.ipynb`.
4. Select the `.venv/bin/python` interpreter from the kernel picker in the upper-right corner.
5. Run individual cells with the play button beside each cell, or use **Run All**.

The selected interpreter is saved for the workspace, so subsequent notebook sessions should use it automatically.

### If VS Code cannot start Jupyter

Use the Command Palette (`Cmd+Shift+P`) and run **Python: Select Interpreter**. Select the interpreter at:

```text
.venv/bin/python
```

Then return to the notebook and select `.venv/bin/python` from the kernel picker. If the kernel does not appear, run **Developer: Reload Window** from the Command Palette and select the interpreter again.
