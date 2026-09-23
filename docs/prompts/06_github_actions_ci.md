# Prompt 6 — GitHub Actions CI

Copy everything below into the agent.

```text
# Task: add GitHub Actions CI for CodeGraph

Working directory: D:\CodeGraph
Project: Python + pytest

Create: .github/workflows/ci.yml

Requirements:
- Trigger on push and pull_request
- Run on ubuntu-latest and windows-latest
- Python 3.10 and 3.12
- Steps: checkout, setup-python, pip install -e ".[dev]", ruff check src/ tests/, pytest -q
- Do not run Dgraph in CI
- If ruff is missing from dev deps, add it to pyproject.toml

Output:
1. Full .github/workflows/ci.yml
2. pyproject.toml dev dependency delta (if any)
3. Commit commands

No explanations.
```
