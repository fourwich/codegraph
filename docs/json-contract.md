# JSON contract

Editors and scripts consume these shapes, so they are a contract rather than an
implementation detail. The VSCode extension calls `codegraph why --json`; scripts
call `index`, `graph` and `decisions`. Every decision object comes from one
serializer (`models.decision_to_dict`), so the four commands cannot drift apart.

Guarantees:

- **Additive changes only.** New keys may appear; existing keys keep their name
  and type. A consumer must ignore keys it does not know.
- **stdout is only the document.** Progress and warnings go to stderr, so
  `codegraph index . --json | jq .nodes` works.
- **Exit codes carry the answer.** `0` means the command produced data; `1` means
  the index has no answer for this query; `2` means a bad argument (unparseable
  date, unknown ref). A JSON document is still printed when the exit code is `1`.
- **No fabricated records.** An empty `decisions` array means "nothing is
  recorded", never "we guessed nothing".

## `codegraph why <file>:<line> --json`

```json
{
  "file": "src/codegraph/storage.py",
  "line": 200,
  "node": {
    "uid": "src/codegraph/storage.py::function::insert_nodes@199::329d59c29957",
    "kind": "function",
    "name": "insert_nodes",
    "file_path": "src/codegraph/storage.py",
    "line_start": 199,
    "line_end": 223,
    "language": "python",
    "commit_sha": "329d59c29957eb1a28d526f05b937c7aaecc70a4"
  },
  "decisions": [ /* decision objects, at most 10 */ ],
  "binding": "line",
  "related": [ /* decisions that govern the file, when decisions is empty */ ]
}
```

- `node` is the innermost live symbol covering the line, or `null` when no symbol
  covers it (a module docstring, an import, a blank line).
- `binding` is `line`, `file`, `commit`, `dir` or `none` — how the answer was
  reached. A caller that only trusts line-level evidence should check it.
- `related` is the file-level fallback: the file is governed by these decisions
  even though nothing is bound to this exact line. It is empty whenever
  `decisions` is non-empty.

A decision object:

```json
{
  "uid": "docs/adr/001-use-sqlite-default.md::decision::adr@1",
  "content": "Use SQLite (stdlib `sqlite3`) as the store under `.codegraph/graph.db`.",
  "reason": "CodeGraph needs a local store ...",
  "alternatives": ["Dgraph first (rejected for MVP: requires Docker and ops setup)."],
  "status": "accepted",
  "source": "adr",
  "source_ref": "ADR 001-use-sqlite-default",
  "timestamp": "2026-10-03T06:29:45.821346+00:00",
  "author": "",
  "file_path": "docs/adr/001-use-sqlite-default.md",
  "line": null,
  "constraints": ["Install and demos work offline with no Docker."],
  "confidence": 0.8,
  "category": "design",
  "tier": "decision"
}
```

`tier` is `decision` (states a reason or a rejected alternative) or `event` (plain
history, only returned with `--include-events`). `category` is `design` or
`dependency` (only returned with `--include-dependency`). `status` is `accepted`,
`superseded` or `rejected`.

## `codegraph index <path> --json`

```json
{
  "root": "D:\\CodeGraph",
  "commits": 2,
  "nodes": 1450,
  "edges": 3203,
  "decisions": 30
}
```

One line, printed at the end of the run. Use `--depth N` and `--full` to control
how much history is re-read.

## `codegraph graph --at <date> --scope <path> --json`

```json
{
  "date": "2026-10-29",
  "scope": "src",
  "nodes": 285,
  "edges": 533,
  "decisions": 0,
  "summary": ["Structure: function make_console_streams_safe @ src/codegraph/__init__.py:8-19"],
  "decision_records": [ /* decision objects */ ]
}
```

`summary` is human-readable prose, not a stable machine format — parse
`decision_records` and the counts instead.

## `codegraph decisions --json`

```json
{
  "file": null,
  "count": 19,
  "decisions": [ /* decision objects, oldest first with --timeline */ ]
}
```

`file` echoes the `--file` filter, `null` when every file is listed.

## Other JSON output

`conflicts --format json` and `diff --format json` predate the `--json` flag and
keep their own shapes (`{"conflicts": [...]}` and a list of decision deltas). They
are not consumed by the editor extension.

## Reproduce

```bash
codegraph index . --json | jq .nodes
codegraph why src/codegraph/storage.py:200 --json | jq '.decisions[0].reason'
codegraph graph --at 2026-10-29 --scope src --json | jq '.nodes'
codegraph decisions --json | jq '.count'
```

The shapes are pinned by `tests/test_json_contract.py`.
