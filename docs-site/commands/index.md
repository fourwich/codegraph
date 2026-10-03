# codegraph index

Parse sources across Git history and persist the graph.

```bash
codegraph index <path> [--depth N] [--use-llm] [--json]
```

## Options

- `--depth` — max commits to walk (default 100)
- `--use-llm` — optional Ollama extraction when rules miss
- `--json` — machine-readable summary

## Example

```bash
codegraph index . --depth 50
```
