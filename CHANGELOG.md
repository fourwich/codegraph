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

## Removed

- Conventional-commit subjects are no longer presented as decisions; they stay queryable as events with `--include-events`.
- The generic `use` / `avoid` opposite pair, which matched inside ordinary English words.
- The bundled sample decisions. `SAMPLE_DECISIONS` was written into the graph whenever a repository recorded no rationale, so a project with no decisions was shown five invented ones (including "PR #48 · Issue #31"). `why` now reports that it has no record instead.
- The Dgraph backend and the `--backend` flag on every command ([ADR-006](docs/adr/006-drop-dgraph-backend.md)): `src/codegraph/graph/` (503 lines), `docker-compose.yml`, `.env.example`, `pydgraph`, the Dgraph tests and the `codegraph.backend` editor setting. One of its paths printed sample data, one ignored the flag, one always crashed, and no shipped query needed a graph database.
- `docs/prompts/`, an internal agent-prompt pack that did not belong in a public repository.
