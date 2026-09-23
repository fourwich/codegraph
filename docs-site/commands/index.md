# codegraph index

Parse sources across Git history and persist the graph.

```bash
codegraph index <path> [--depth N] [--backend sqlite|dgraph] [--use-llm] [--json]
```

## Options

- `--depth` — max commits to walk (default 100)
- `--backend` — `sqlite` (default) or `dgraph`
- `--use-llm` — optional Ollama extraction when rules miss
- `--json` — machine-readable summary

## Example

```bash
codegraph index . --depth 50
```
