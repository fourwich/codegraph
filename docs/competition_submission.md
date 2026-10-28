# Creator Colosseum — CodeGraph submission copy

GitHub: https://github.com/fourwich/codegraph  
Live demo: https://fourwich.github.io/codegraph  
Verified locally: **149 tests passing** · **8 CLI commands** · **7 languages**

---

## 1. Elevator pitch (pick one)

**Recommended:**  
CodeGraph answers “why is this line here?” with a decision card — not just git blame.

Alternates:
- Code structure, git history, and design decisions in one queryable graph.
- The decision memory layer for your codebase — ask why, get provenance.

## 2. Project Story

### What inspired me

I kept hitting the same wall while reading code and building my own tools: a line looked arbitrary, and no tool could explain it. `git blame` told me who edited it last. Search told me where a string appeared. Old PR threads had the real reason — if I could find them. ADR docs existed in theory, but nobody on small projects kept them up to date.

I am 15 and mostly self-taught. When I do not understand a design choice, I cannot just walk over to a senior engineer. I needed a machine-readable answer to “why?” I imagined one graph where structure, time, and decisions hang together, so a single query could join them.

### What I learned

I learned that parsing code for real is different from writing a toy tokenizer. tree-sitter gives a solid AST, but mapping functions, methods, classes, and calls into stable IDs and edges is where design decisions matter. Supporting seven languages taught me to keep a narrow `BaseParser` interface and resist language-specific special cases leaking upward. Java methods, Go functions, Rust `impl` blocks, and C++ declarators all needed different name extraction — yet the storage layer only ever sees `kind`, `name`, and a line range.

Working with graphs taught me storage trade-offs. SQLite is perfect for a local MVP and for tests that must stay fast — one file, no server, no Docker. I also shipped a small FastAPI + Cytoscape UI and a VSCode extension that shells out to `codegraph why --json`, which taught me more about product packaging than about algorithms: TypeScript builds, Webview HTML, and a stable JSON contract for editors.

The hardest lesson came from deleting code. I had built an optional Dgraph backend and advertised it; an audit showed `--backend dgraph` returned sample data in one path, was silently ignored in another, and crashed in a third. I removed all 503 lines rather than keep a feature I could not stand behind ([ADR-006](adr/006-drop-dgraph-backend.md)).

Finally I learned honesty under deadline pressure. A student project can easily overclaim. I removed the bundled sample decisions so nothing is fabricated, measured a real index run, and wrote status numbers only after running `pytest -q` and `codegraph --help`.

### How I built it

I built CodeGraph in stages so each one stayed runnable.

1. **MVP** — Typer CLI, pydantic models, Rich decision cards, SQLite schema.
2. **Real Git** — GitPython history walks; every CodeNode version carries `valid_from` / `valid_to`; `graph --at` filters live nodes and live edges.
3. **Decisions** — rule-based extraction from commit messages, ADR markdown, and CHANGELOG sections (keywords such as *because* / *instead of*), graded into `decision` and `event` tiers so a commit subject is never presented as a design rationale.
4. **Multi-language** — tree-sitter parsers for TypeScript/JavaScript, Python, Java, Go, Rust, and C++ behind one registry.
5. **Web + export** — `codegraph serve` (FastAPI + Cytoscape) and `codegraph export --for-ai` context packs for coding agents.
6. **Editor + LLM** — VSCode “Show decision” using JSON output; optional Ollama extraction (`--use-llm`) that degrades to rules when offline.

Each stage shipped with tests. Parallel parsing (`--jobs`) and incremental HEAD state exist for larger trees, but this repository’s self-index is still the demo path. Today the test suite reports **149 passing tests**. The CLI exposes **eight commands**: `index`, `why`, `graph`, `decisions`, `conflicts`, `export`, `serve`, and `diff`.

### Challenges I faced

**Time travel vs. speed.** Versioning every historical node makes `graph --at` honest, but edge counting must require both endpoints live at the chosen date. I added scoped SQL and kept benchmarks: on this repo the `why` lookup takes ~2.3 ms of query time (median of 50 runs; ~0.36 s wall time, dominated by interpreter start) and the `graph --at` decision query ~0.1 ms.

**Seven grammars, one contract.** Each language names functions and calls differently. I standardized on `parse_text` + call-site tuples so edge extraction runs after merging nodes — otherwise parallel per-file parsing drops cross-file calls. Fixtures for `.java` / `.go` / `.rs` / `.cpp` lock that contract in tests.

**Dgraph upserts.** My first storage plan was an optional Dgraph backend behind `--backend dgraph`, and it cost me the most valuable week of the project. The flag shipped before the backend worked: one path printed sample decisions instead of the query result, `serve` validated the flag and then ignored it, and `export` raised `AttributeError` on every call. I removed all 503 lines ([ADR-006](adr/006-drop-dgraph-backend.md)). The lesson: an unfinished feature behind a flag still has to be honest, and deleting it is cheaper than defending it.

**Noise in decision extraction.** Rules first; LLM only when a commit lacks rationale keywords, and LLM confidence is capped at 0.7 so it cannot outrank explicit reasoning. When Ollama is offline the CLI warns and continues — never fail the whole index. Every record is also graded: only records that state a reason or a rejected alternative are shown as decisions; commit subjects stay as `event` history. On Express.js that is **5 decisions out of 204 records** — a small, checkable number instead of an inflated one.

### Why not just ask an AI?

Coding assistants are brilliant at generating code in front of them, but they cannot open a two-year-old closed issue, follow a superseded ADR, or quote the PR review that blocked a shortcut. They see the file you paste; they do not see the graph of constraints around it. CodeGraph does not replace the model — it gives the model (and the human) a provenance layer: the actual commit, the actual decision, and the line it justifies. That is the difference between a confident guess and a checkable answer.

### What's next

Only unfinished work: richer conflict rules, publishing the VSCode extension to the Marketplace, and performance tuning on larger monorepos. CI now runs ruff, mypy, pytest and a materials check on a 6-job matrix (Ubuntu/Windows/macOS × Python 3.10/3.12) and is green; the next step is publishing to PyPI so `pip install` works without cloning. No vaporware — if it is not in the repo or tests, it is not in this story.

## 3. Built with (tags)

Python, Typer, Rich, pydantic, tree-sitter, tree-sitter-typescript, tree-sitter-python, tree-sitter-java, tree-sitter-go, tree-sitter-rust, tree-sitter-cpp, GitPython, SQLite, FastAPI, Uvicorn, Cytoscape.js, httpx, Ollama, pytest, TypeScript, VS Code Extension API, GitHub Actions, MIT License

*(JS uses the TypeScript grammar; VS Code extension ships as `codegraph-vscode-0.1.0.vsix`.)*

## 4. Try it out

- GitHub repository: https://github.com/fourwich/codegraph
- Live demo (product site): https://fourwich.github.io/codegraph
- Local CLI: see README Quick start (`pip install -e ".[dev]"` then `codegraph index .`)
- Local visualizer: `codegraph serve` → http://127.0.0.1:8080/

## 5. Likely Q&A

**1. Why SQLite and not a graph database?**  
Because no shipped query needs one. SQLite gives a zero-setup local store, fast tests and honest time travel, and every query the CLI actually makes is a scoped lookup. I did build the Dgraph path first and removed it: it was 503 lines of untested client code, `--backend dgraph` returned sample data on one path and was ignored on another, and nothing in the CLI performs a multi-hop traversal. A native graph store comes back when a real query justifies it — [ADR-006](adr/006-drop-dgraph-backend.md).

**2. How does time travel work?**  
Every CodeNode version stores `valid_from` / `valid_to` from Git commits. `graph --at DATE` keeps nodes where `valid_from <= DATE` and `valid_to` is null or `>= DATE`. Edges count only when both endpoints are live at that date.

**3. How do you keep decision extraction accurate?**  
Rules first: rationale keywords in commit messages, ADR headings, CHANGELOG Changed/Removed sections. A record is only presented as a decision when it states a reason (`because …`, `to fix …`) or a rejected alternative (`instead of X`); commit subjects and release-note lines are stored as `event` history and hidden unless `--include-events` is passed. Optional Ollama fills gaps only when rules find nothing, with confidence capped at 0.7. Precision is measured, not asserted: `python scripts/eval_decision_precision.py <repo>`.

**4. How do you handle seven languages?**  
One `BaseParser` interface: `parse_text` returns nodes; call sites are recorded then merged into `uses` / `contains` edges. Language files only map AST kinds to function/class/variable — no language logic in storage.

**5. Doesn’t LLM fallback add noise?**  
It can. That is why it is opt-in (`--use-llm`), requires a local Ollama, and never exceeds 0.7 confidence. If Ollama is down we warn and continue with rules only.

**6. Why not just ask an AI?**  
AI sees the code you paste, not a closed issue from two years ago or the PR that rejected an option. CodeGraph attaches the real commit, the real decision, and the line it justifies — so answers are checkable, not guessed. It is a provenance layer for humans and models, not a replacement for either.

**7. How is this different from Joern or CodeQL?**  
Those tools excel at vulnerability and deep semantic queries. CodeGraph optimizes for **provenance**: linking a line to design decisions and history with a small local CLI. Different job — complementary, not a replacement.

**8. Biggest technical hurdle?**  
Correct historical edges. Naive per-file parsing drops cross-file calls and time filters counted dead edges. The fix was merge-then-extract edges and live-endpoint edge counts.

**9. If you started over, what would you change?**  
I would define the versioned-node schema on day one, and add `--json` earlier so editors and tests share one contract. I would also not put an unfinished backend behind a flag: either it works in a test, or it does not ship.

**10. Any commercial path?**  
Possible wedges: enterprise onboarding, refactoring safety, or AI-agent context packs. For now it is MIT open source; no revenue claims.

**11. Why build this at 15?**  
I needed the tool myself and could not ask a staff engineer “why is this line here?” Building it taught parsing, graphs, APIs, and shipping under an honest scoreboard (149 tests, 8 commands, 7 languages).
