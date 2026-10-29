# CodeGraph for VSCode

Right-click a line → **CodeGraph: Show decision** to see why that line exists.

The panel shows the decision bound to that line and labels how it was found
(`line`, `file`, `commit`, `dir`). When nothing is bound to the exact line but the
file is governed by an ADR, the panel lists those governing decisions instead of
claiming there is no record.

## Commands

- `CodeGraph: Show decision`
- `CodeGraph: Index workspace`
- `CodeGraph: Open web visualizer`

## Settings

- `codegraph.cliPath` (default `codegraph`)
- `codegraph.autoIndex`

## Develop

```bash
npm install
npm run compile
# F5 in VSCode to launch Extension Development Host
```

Requires the `codegraph` CLI on PATH (or set `codegraph.cliPath`). The panel reads
`codegraph why --json`; the contract is documented in
[`docs/json-contract.md`](../docs/json-contract.md) and pinned by tests.
