# Creator Colosseum — CodeGraph submission copy

GitHub: https://github.com/fourwich/codegraph  
Live demo: https://fourwich.github.io/codegraph

---

## 1. Elevator pitch (pick one)

**Recommended:**  
CodeGraph answers “why is this line here?” with a decision card — not just git blame.

Alternates:
- Code structure, git history, and design decisions in one queryable graph.
- The decision memory layer for your codebase — ask why, get provenance.

## 2. Project Story (600-800 words)

### What inspired me

I kept running into the same wall while reading code and building my own tools: a line looked arbitrary, and no tool could explain it. `git blame` told me who edited it last. Search told me where a string appeared. Old PR threads had the real reason — if I could find them. ADR docs existed in theory, but nobody on small projects kept them up to date.

I am 15 and mostly self-taught. When I do not understand a design choice, I cannot just walk over to a senior engineer. I needed a machine-readable answer to “why?” I imagined one graph where structure, time, and decisions hang together, so a single query could join them.

### What I learned

I learned that parsing code for real is different from writing a toy tokenizer. tree-sitter gives a solid AST, but mapping functions, classes, and calls into stable IDs and edges is where design decisions matter. I also learned storage trade-offs: SQLite is perfect for a local MVP, while a real graph database earns its keep for multi-hop questions.

Working in public taught me packaging: `pyproject.toml`, editable installs, tests that exercise the CLI, and English-only user-facing text for an international competition. I also learned to scope ruthlessly — ship four commands that work instead of seven that half-work.

### How I built it

CodeGraph is a Python CLI on Typer and Rich, with pydantic models shared across layers. The MVP path is:

1. Walk a repo and parse TypeScript and Python with tree-sitter.
2. Extract CodeNodes (function, class, variable) and edges (uses, contains, defined_by).
3. Store the graph in SQLite under `.codegraph/graph.db`.
4. Answer `codegraph why file:line` with a decision card: location, decision, reason, alternatives, source, status, constraints, confidence.
5. Answer `codegraph graph --at DATE` with a historical snapshot table.

The product site is a static page with a terminal demo and a small SVG graph hero. It is intentionally simple so judges can try the idea without installing anything.

### Challenges I faced

The hardest part was not syntax. It was keeping the contract stable: the same models feed the CLI today and will feed Dgraph later. Call-site resolution — linking a call to the right caller and callee across a file — forced me to think about scopes and naming.

Another challenge was honesty. A student project can easily overclaim. I kept sample decisions explicit, labeled the Dgraph backend as in progress, and measured a real index run (on the order of tens of nodes and hundreds of edges on this repo) instead of inventing users or stars.

Time zones and formats also bit me: dates in `--at`, paths with different separators, and Windows vs Unix line endings. Small things that only show up when you actually run the tool.

### What's next

I am finishing an optional Dgraph backend for multi-hop queries and time-travel filters. Then: conflict detection across accepted decisions, a local Cytoscape web view, and an export pack for coding agents so they can bring provenance into their context.

The goal is modest and concrete: when someone asks why a line exists, CodeGraph should return the decision — or honestly say there is not enough record yet.

## 3. Built with (tags)

Python, Typer, Rich, pydantic, tree-sitter, tree-sitter-typescript, tree-sitter-python, SQLite, pytest, uv, HTML, CSS, JavaScript, SVG, GitHub Actions, Docker, Dgraph (optional), pydgraph, dotenv, Git, Open source, MIT License, Developer tools, Code analysis, Graph database

## 4. Try it out

- GitHub repository: https://github.com/fourwich/codegraph
- Live demo (product site): https://fourwich.github.io/codegraph
- Local CLI: see README Quick start

## 5. Likely Q&A

**1. What problem does this solve?**  
It connects code lines to design decisions. Blame shows who; CodeGraph tries to show why, including rejected alternatives and constraints.

**2. Why not just use git blame and search?**  
Those tools answer “who” and “where.” They do not join structure, time, and decisions into one query.

**3. Is this production-ready?**  
No. It is an MVP: four CLI commands, tree-sitter parsing, SQLite storage, sixteen tests. Dgraph is optional and still in progress.

**4. How accurate is the parsing?**  
tree-sitter handles TypeScript and Python well for top-level functions and classes. Nested and dynamic cases are simplified. Call edges use name matching, not full type inference.

**5. Where do decisions come from?**  
MVP ships bundled sample decisions. The next step is extracting them from PRs, issues, and ADR files automatically.

**6. Why SQLite first and Dgraph later?**  
SQLite keeps the demo zero-ops. Dgraph is the right long-term store for multi-hop graph queries and time travel.

**7. Can it time-travel the code graph?**  
The `graph --at` command filters by date and reports a snapshot. Full validity windows per node are modeled and will deepen with Dgraph.

**8. What did a 15-year-old learn from this?**  
Packaging a real project, writing tests around a CLI, keeping a stable data contract, and refusing to fake metrics for a pitch.

**9. What is the business or open-source angle?**  
Open source under MIT. The wedge is developer tooling: better onboarding, safer refactors, and better context for AI coding agents.

**10. What would you do with more time?**  
Automatic decision extraction, conflict detection, a web graph view, and agent export packs. Then dogfood it on larger repos.

---

Facts only: 16 tests passing as of local verification. Index sample sizes vary by repository; see README for commands to reproduce.
