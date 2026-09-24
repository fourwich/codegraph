# CodeGraph

![tests](https://img.shields.io/badge/tests-49%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

**English:** Turn code structure, git history, and design decisions into one queryable graph — ask “why is this line here?” and get a decision card, not just a blame line.

**中文：** 把代码结构、历史变更和设计决策变成一张可查询的图。不只回答「谁改的」，更回答「为什么这么写」。

**Status:** alpha · 7 CLI commands · 6 languages · SQLite default · optional Dgraph

See [docs/architecture.md](docs/architecture.md) for the full architecture overview.

- GitHub: https://github.com/fourwich/codegraph
- Live demo: https://fourwich.github.io/codegraph

## Status

Verified with `pytest -q` and `codegraph --help` (49 tests passing).

- [x] Product site (HTML / CSS / JS)
- [x] CLI with 7 commands (`index` / `why` / `graph` / `decisions` / `conflicts` / `export` / `serve`)
- [x] tree-sitter parsing (6 languages)
- [x] SQLite storage
- [x] Real Git history traversal
- [x] Decision extraction from commits, ADRs, CHANGELOG
- [x] Real time-travel queries (`graph --at`)
- [x] 49 tests passing
- [x] Local web visualization (`codegraph serve`)
- [x] VSCode extension sources + `why --json`
- [x] Optional Ollama hook (`--use-llm`)
- [ ] Dgraph backend (client + flag done; live cluster optional)

## Language support

| Language | Extensions | Parser |
|---|---|---|
| TypeScript | `.ts` `.tsx` | `treesitter_ts.py` |
| Python | `.py` | `treesitter_py.py` |
| Java | `.java` | `treesitter_java.py` |
| Go | `.go` | `treesitter_go.py` |
| Rust | `.rs` | `treesitter_rust.py` |
| C++ | `.cpp` `.cc` `.cxx` `.hpp` `.hh` `.hxx` `.h` | `treesitter_cpp.py` |

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

## Commands (7)

```bash
codegraph --help
codegraph index . [--depth N] [--backend sqlite|dgraph] [--use-llm] [--json]
codegraph why src/auth/session.ts:42 [--json]
codegraph graph --at 2024-11-02 --scope src
codegraph decisions --file src/auth/session.ts --timeline
codegraph conflicts --scope src
codegraph export --for-ai --scope src
codegraph serve --port 8080
```

## Tech stack

| Layer | Choice |
|---|---|
| CLI | Python · Typer · Rich |
| Models | pydantic |
| Parsing | tree-sitter (+ language grammars) |
| Git | GitPython |
| Storage | SQLite (default) · Dgraph (optional) |
| Web | FastAPI · Uvicorn · Cytoscape.js |
| LLM (optional) | Ollama via httpx |
| Editor | VSCode extension (TypeScript) |
| Tests | pytest |

## Tests

```bash
pytest -q
# with coverage
pytest --cov=src/codegraph
```

## Optional: Dgraph backend

SQLite remains the default. Dgraph is optional for multi-hop graph queries.

```bash
# 1) Start Dgraph (requires Docker)
docker compose up -d

# 2) Index with Dgraph
.venv\Scripts\codegraph.exe index . --backend dgraph

# 3) Same commands accept --backend dgraph
.venv\Scripts\codegraph.exe why src/auth/session.ts:42 --backend dgraph
.venv\Scripts\codegraph.exe graph --at 2024-11-02 --backend dgraph
.venv\Scripts\codegraph.exe conflicts --scope src --backend dgraph
.venv\Scripts\codegraph.exe export --for-ai --scope src --backend dgraph
```

Dgraph UI: http://localhost:8080/?latest  
If Dgraph is down, `--backend dgraph` exits with code `3`. SQLite mode is unchanged.

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
