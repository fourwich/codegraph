# CodeGraph

**English:** Turn code structure, git history, and design decisions into one queryable graph — ask “why is this line here?” and get a decision card, not just a blame line.

**中文：** 把代码结构、历史变更和设计决策变成一张可查询的图。不只回答「谁改的」，更回答「为什么这么写」。

**Status:** alpha MVP · CLI usable · Dgraph backend optional / in progress

- GitHub: https://github.com/fourwich/codegraph
- Live demo: https://fourwich.github.io/codegraph

## Quick start

```bash
# recommended: uv
uv venv
uv pip install -e ".[dev]"

# or: venv + pip
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
```

## Commands

```bash
codegraph --help
codegraph index .
codegraph why src/auth/session.ts:42
codegraph graph --at 2024-11-02 --scope src
codegraph decisions --file src/auth/session.ts --timeline
```

## Tests

```bash
pytest -q
# with coverage
pytest --cov=src/codegraph
```

## Optional: Dgraph backend

SQLite remains the default. Dgraph is optional for multi-hop graph queries.

```bash
docker compose up -d
.venv\Scripts\codegraph.exe index . --backend dgraph
.venv\Scripts\codegraph.exe why src/auth/session.ts:42 --backend dgraph
.venv\Scripts\codegraph.exe graph --at 2024-11-02 --backend dgraph
```

See `.env.example` for `DGRAPH_ALPHA`. If Dgraph is down, `--backend dgraph` exits with code `3`.

## Project layout

```text
src/codegraph/
  cli.py          # Typer entrypoint
  models.py       # CodeNode / Edge / Decision
  storage.py      # SQLite graph store
  parser/         # tree-sitter TS + Python
  graph/          # optional Dgraph backend
  commands/       # index / why / graph / decisions
tests/
docs/             # demo script, prompts, submission copy
index.html        # product site
```

## Docs

- Architecture overview (PDF source): `docs/architecture_overview.txt`
- 60s demo voiceover: `docs/demo_voiceover.md`
- Competition copy: `docs/competition_submission.md`
- Contributing: `CONTRIBUTING.md`

## License

MIT
