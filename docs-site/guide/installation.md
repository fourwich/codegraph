# Installation

```bash
git clone https://github.com/fourwich/codegraph
cd codegraph
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```
