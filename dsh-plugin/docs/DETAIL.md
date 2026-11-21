# CodeGraph

`git blame` tells you **who** changed a line. CodeGraph tells you **why** the line
is written that way — from the record the project itself wrote down: an ADR, a
changelog entry, or a commit body that states a reason or a rejected alternative.

This plugin gives the agent two tools over the [codegraph](https://pypi.org/project/codegraphx/)
CLI.

## Tools

| Tool | What it answers |
|---|---|
| `codegraph_index` | Index a repository: parse the code, walk its git history, store the graph in `<root>/.codegraph/graph.db`. |
| `codegraph_why` | Given `path:line`, return the decision card bound to that line, or the decisions that govern the file when nothing is bound to the exact line. |

## Requirements

The CLI must be installed and on `PATH`:

```bash
pip install codegraphx
```

If it lives somewhere else, set `cliPath` in the plugin's configuration.

## Usage

The agent indexes once per repository, then asks per line. Typical exchange:

```
> why does storage.py:200 open a SQLite connection here?

codegraph_index { root: "D:/repo" }
codegraph_why   { location: "src/storage.py:200" }
```

A card looks like this:

```
function insert_nodes — src/storage.py:199-223

1. Use SQLite (stdlib `sqlite3`) as the store under `.codegraph/graph.db`.
   reason: judges and developers must run the CLI without operating a database
           server. Multi-hop graph queries matter later, but day-one reliability
           and zero setup matter more.
   rejected: Dgraph first (requires Docker and ops setup) | In-memory only
             (cannot time-travel after the process exits)
   source: adr · ADR 001-use-sqlite-default
```

## Honest limitations

- **A record exists only if the project wrote one.** CodeGraph never invents a
  reason. When a project records none, `codegraph_why` reports no record, and the
  agent gets `found: false` rather than a plausible guess.
- **Not every line is reachable.** Measured across seven real repositories, 12–40%
  of sampled locations returned a line-level card. A changelog decision links to
  one specific line, not to every line it influenced. The file-level fallback
  covers part of the gap.
- **Docking scores and similar numbers are not involved here.** The tools read a
  local SQLite file; nothing leaves the machine and no network call is made.
- **Indexing reads git history.** A shallow clone carries only the recent commits,
  so older decisions will not be found. `depth` controls how far back it reads.

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `cliPath` | `codegraph` | Executable name or absolute path of the CLI. |
| `timeoutMs` | `120000` | How long one CLI call may run. |

See [the project page](https://fourwich.github.io/codegraph/) for the measured
numbers on real repositories, including the ones that came out low.
