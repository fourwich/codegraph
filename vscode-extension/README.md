# CodeGraph for VSCode

Right-click a line → **CodeGraph: Show decision** to see why that line exists.

## Commands

- `CodeGraph: Show decision`
- `CodeGraph: Index workspace`
- `CodeGraph: Open web visualizer`

## Settings

- `codegraph.cliPath` (default `codegraph`)
- `codegraph.backend` (`sqlite` | `dgraph`)
- `codegraph.autoIndex`

## Develop

```bash
npm install
npm run compile
# F5 in VSCode to launch Extension Development Host
```

Requires the `codegraph` CLI on PATH (or set `codegraph.cliPath`).
