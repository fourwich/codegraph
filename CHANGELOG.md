# Changelog

## Changed

- Index walks real Git history and versions CodeNodes with valid_from / valid_to because time travel must reflect actual commits rather than a static snapshot.
- Decision extraction prefers commit messages, ADRs, and CHANGELOG over bundled samples because provenance should point at real sources.
- A second `index` merges into the stored graph instead of clearing it, so re-running the command no longer destroys Git history.
- Decision records carry a `decision` / `event` tier, and only records that state a reason or a rejected alternative are shown as decisions.
- ADRs and CHANGELOG entries bind to the code they name, so a design rule can be reached from the line it governs.
- A decision that claims more than 10 files or 250 lines keeps only a commit-level binding, so one noisy commit cannot claim thousands of lines.
- Conflict detection matches whole words and requires a shared topic, so unrelated documents in one folder no longer contradict each other.
- `codegraph index --json` writes progress to stderr, so stdout is a single JSON document that editors can parse.
- `codegraph why` accepts an absolute path, which is what an editor hands over for the current file.
- The web API filters by scope instead of widening it: `/api/graph` used to fall back to every decision in the repository when a scope had none, and reported the unscoped count in its stats. A scope now matches on a path boundary (`src` no longer matches `src2`) and a decision is in scope when it was recorded there **or** governs code there, so an ADR bound with `governs:` shows up for the files it governs.
- `/api/timeline` honours its `scope` parameter. It previously ignored it, so the slider ticks came from every file in the graph.
- `/api/why` uses the same resolution as the `codegraph why` command, including the symbol-range lookup, so the UI and the CLI cannot disagree about whether a decision exists for a line.
- `codegraph serve` opens the browser only after the port is bound, instead of before uvicorn starts.
- C++ in-class methods are nodes with the class as their parent, and their calls produce edges. Name resolution walks the declarator chain, so `int Calculator::compute(int)` and `int spin(int n)` inside a class are no longer anonymous, and a prototype (`int helper(int);`) is a function while `int limit = 3;` is not.
- Rust `impl` blocks and Go methods now hang off the type they belong to: `impl Scale for Meter { fn scale }` attaches to `Meter`, and `func (c *Calculator) Add()` attaches to `Calculator`. Previously `impl_item` and `type_declaration` were dead entries in the kind maps.
- Call edges resolve against every symbol live at that commit, not just the file being parsed. The git path previously produced **zero** cross-file `uses` edges while the working-tree path produced them, so the same repository gave two different graphs. Express: 1308 → 3951 `uses` edges, 2515 of them cross-file.
- Git and working-tree parsing now share one edge rule; `ingest_commit` versions all changed files first, then resolves edges.
- A call to a name defined in several files prefers the definition in the caller's own file, and only fans out across files when nothing local matches. `helper()` next to its definition no longer links to every same-named `helper` in the repository: Express edges 2409 → 1460, and the share of cross-file edges pointing at an ambiguous name fell from 21% to 17% on this repository.
- The public materials carry only measured numbers, and the CI suite is green again: 22 lint findings and one real typing bug had kept `ruff` failing since 2026-09-24, so `mypy` and `pytest` never ran in CI.
- Indexing reuses one Git repo handle and caches each commit's parsed diff, because decision binding asked for the same commit once per record: on `got`, 85 records shared 50 commits, and the redundant git calls cost a third of the index time. `got` depth 200: 111s → 75s, identical graph.
- `codegraph why` on a line with no bound record now reports the decisions that govern the whole file, so a line inside a governed module returns that module's ADR instead of "no record". The JSON payload gains a `related` array for the same case.
- Date refs use the local calendar, not UTC: a commit's `git log --date=short` date now resolves with `diff` and `graph --at`. Comparing against the UTC date made every date fail for part of the day east of Greenwich (a commit at 00:30 in UTC+8 is still the previous day in UTC), and `graph --at` placed its cut-off eight hours late. Both are covered by timezone tests that do not depend on the machine clock.
- Changelogs are read from `CHANGELOG`, `CHANGES`, `HISTORY` and `NEWS` files in both markdown and reStructuredText, and every bullet is a candidate instead of only a `## Changed` section. The tier classifier keeps the ones with a rationale, so this raises recall without lowering precision: Flask went from **1 decision to 56** on the same checkout, because a Python project ships `CHANGES.rst` rather than `CHANGELOG.md`.
- `codegraph decisions --timeline` works without `--file`: omitting it lists the decisions of every file, which is the natural first look after indexing. `--file` is now a filter instead of a required argument.
- `codegraph graph` and `codegraph decisions` gained `--json`, joining `why` and `index`. All four decision payloads now come from one serializer, and the shapes are documented in [json-contract.md](docs/json-contract.md) and pinned by tests, so the editor extension has a stable contract instead of whatever the models happen to emit.
- Prose decisions bind through a backticked symbol name that is **unique** in the graph, even when it is short and lowercase (`redirect`), while a name shared by several files still needs the distinctive spelling. Flask: 6 → 10 of 56 decisions reachable from a code line.

## Removed

- Conventional-commit subjects are no longer presented as decisions; they stay queryable as events with `--include-events`.
- The generic `use` / `avoid` opposite pair, which matched inside ordinary English words.
- The bundled sample decisions. `SAMPLE_DECISIONS` was written into the graph whenever a repository recorded no rationale, so a project with no decisions was shown five invented ones (including "PR #48 · Issue #31"). `why` now reports that it has no record instead.
- The Dgraph backend and the `--backend` flag on every command ([ADR-006](docs/adr/006-drop-dgraph-backend.md)): `src/codegraph/graph/` (503 lines), `docker-compose.yml`, `.env.example`, `pydgraph`, the Dgraph tests and the `codegraph.backend` editor setting. One of its paths printed sample data, one ignored the flag, one always crashed, and no shipped query needed a graph database.
- `docs/prompts/`, an internal agent-prompt pack that did not belong in a public repository.
- The dead `method` filter in the web UI. No parser emits a node of kind `method` (methods are `function`), so ticking it filtered the graph to nothing.
