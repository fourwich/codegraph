# Creator Colosseum — CodeGraph submission copy

GitHub: https://github.com/fourwich/codegraph  
Live demo: https://fourwich.github.io/codegraph  
Verified locally: **49 tests passing** · **7 CLI commands** · **6 languages**

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

I learned that parsing code for real is different from writing a toy tokenizer. tree-sitter gives a solid AST, but mapping functions, methods, classes, and calls into stable IDs and edges is where design decisions matter. Supporting six languages taught me to keep a narrow `BaseParser` interface and resist language-specific special cases leaking upward. Java methods, Go functions, Rust `impl` blocks, and C++ declarators all needed different name extraction — yet the storage layer only ever sees `kind`, `name`, and a line range.

Working with graphs taught me storage trade-offs. SQLite is perfect for a local MVP and for tests that must stay fast. Dgraph is the right long-term store for multi-hop questions — and its upsert model is less forgiving than SQL. I also shipped a small FastAPI + Cytoscape UI and a VSCode extension that shells out to `codegraph why --json`, which taught me more about product packaging than about algorithms: TypeScript builds, Webview HTML, and a stable JSON contract for editors.

Finally I learned honesty under deadline pressure. A student project can easily overclaim. I kept sample decisions labeled, measured a real index run on this repository, and wrote status numbers only after running `pytest -q` and `codegraph --help`.

### How I built it

I built CodeGraph in stages so each one stayed runnable.

1. **MVP** — Typer CLI, pydantic models, Rich decision cards, SQLite schema.
2. **Real Git** — GitPython history walks; every CodeNode version carries `valid_from` / `valid_to`; `graph --at` filters live nodes and live edges.
3. **Decisions** — rule-based extraction from commit messages, ADR markdown, and CHANGELOG sections (keywords such as *because* / *instead of*), with conventional-commit subjects as weak evidence.
4. **Multi-language** — tree-sitter parsers for TypeScript, Python, Java, Go, Rust, and C++ behind one registry.
5. **Web + export** — `codegraph serve` (FastAPI + Cytoscape) and `codegraph export --for-ai` context packs for coding agents.
6. **Editor + LLM** — VSCode “Show decision” using JSON output; optional Ollama extraction (`--use-llm`) that degrades to rules when offline.

Each stage shipped with tests. Parallel parsing (`--jobs`) and incremental HEAD state exist for larger trees, but this repository’s self-index is still the demo path. Today the test suite reports **49 passing tests**. The CLI exposes **seven commands**: `index`, `why`, `graph`, `decisions`, `conflicts`, `export`, and `serve`.

### Challenges I faced

**Time travel vs. speed.** Versioning every historical node makes `graph --at` honest, but edge counting must require both endpoints live at the chosen date. I added scoped SQL and kept benchmarks: on this repo `why` queries stay well under 1 ms and `graph --at` around 1 ms.

**Six grammars, one contract.** Each language names functions and calls differently. I standardized on `parse_text` + call-site tuples so edge extraction runs after merging nodes — otherwise parallel per-file parsing drops cross-file calls. Fixtures for `.java` / `.go` / `.rs` / `.cpp` lock that contract in tests.

**Dgraph upserts.** Business keys (`node_uid`) must map onto blank nodes and `uid(var)` updates without duplicating history versions. Live clusters are optional; the client and `--backend dgraph` exist, but production hardening is still open.

**Noise in decision extraction.** Rules first; LLM only when a commit lacks rationale keywords, and LLM confidence is capped at 0.7 so it cannot outrank explicit reasoning. When Ollama is offline the CLI warns and continues — never fail the whole index.

### What's next

Only unfinished work: harden the Dgraph backend against a live cluster, richer conflict rules, publish the VSCode extension to the Marketplace, and continue performance tuning on larger monorepos. I would also like CI on every OS matrix to stay green with coverage reports. No vaporware — if it is not in the repo or tests, it is not in this story.

## 3. Built with (tags)

Python, Typer, Rich, pydantic, tree-sitter, tree-sitter-typescript, tree-sitter-python, tree-sitter-java, tree-sitter-go, tree-sitter-rust, tree-sitter-cpp, GitPython, SQLite, FastAPI, Uvicorn, Cytoscape.js, httpx, Ollama, Dgraph, pydgraph, pytest, TypeScript, VS Code Extension API, GitHub Actions, MIT License

*(25 tags; all appear in `pyproject.toml`, `vscode-extension/`, or workflows.)*

## 4. Try it out

- GitHub repository: https://github.com/fourwich/codegraph
- Live demo (product site): https://fourwich.github.io/codegraph
- Local CLI: see README Quick start (`pip install -e ".[dev]"` then `codegraph index .`)
- Local visualizer: `codegraph serve` → http://127.0.0.1:8080/

## 5. Likely Q&A

**1. Why Dgraph instead of Neo4j?**  
Dgraph is a distributed native graph with DQL and upsert blocks, and it matches our multi-hop “decision → code → commit” shape. Neo4j is excellent, but we wanted Apache-2.0 friendly ops and a simple Docker Compose path. SQLite stays default so the demo never requires either.

**2. How does time travel work?**  
Every CodeNode version stores `valid_from` / `valid_to` from Git commits. `graph --at DATE` keeps nodes where `valid_from <= DATE` and `valid_to` is null or `>= DATE`. Edges count only when both endpoints are live at that date.

**3. How do you keep decision extraction accurate?**  
Rules first: rationale keywords in commit messages, ADR headings, CHANGELOG Changed/Removed sections, plus conventional-commit subjects as weak evidence. Optional Ollama fills gaps only when rules find nothing, with confidence capped at 0.7.

**4. How do you handle six languages?**  
One `BaseParser` interface: `parse_text` returns nodes; call sites are recorded then merged into `uses` / `contains` edges. Language files only map AST kinds to function/class/variable — no language logic in storage.

**5. Doesn’t LLM fallback add noise?**  
It can. That is why it is opt-in (`--use-llm`), requires a local Ollama, and never exceeds 0.7 confidence. If Ollama is down we warn and continue with rules only.

**6. How is this different from Joern or CodeQL?**  
Those tools excel at vulnerability and deep semantic queries. CodeGraph optimizes for **provenance**: linking a line to design decisions and history with a small local CLI. Different job — complementary, not a replacement.

**7. Biggest technical hurdle?**  
Correct historical edges. Naive per-file parsing drops cross-file calls and time filters counted dead edges. The fix was merge-then-extract edges and live-endpoint edge counts.

**8. If you started over, what would you change?**  
I would define the SQLite/Dgraph schema for versioned nodes on day one, and add `--json` earlier so editors and tests share one contract.

**9. Any commercial path?**  
Possible wedges: enterprise onboarding, refactoring safety, or AI-agent context packs. For now it is MIT open source; no revenue claims.

**10. Why build this at 15?**  
I needed the tool myself and could not ask a staff engineer “why is this line here?” Building it taught parsing, graphs, APIs, and shipping under an honest scoreboard (49 tests, 7 commands, 6 languages).
