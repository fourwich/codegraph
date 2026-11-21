# CodeGraph for DeepSeek Harness

A DSH plugin that gives an agent two tools over the [codegraph](https://pypi.org/project/codegraphx/) CLI:

| Tool | Answers |
|---|---|
| `codegraph_index` | Index a repository: parse the code, walk its git history, store the graph in `<root>/.codegraph/graph.db`. |
| `codegraph_why` | Given `path:line`, return the decision bound to that line, or the decisions governing the file when nothing is bound to the exact line. |

`git blame` says who changed a line. `codegraph_why` says why the line is written
that way, from the record the project itself wrote down — an ADR, a changelog entry,
or a commit body that states a reason or a rejected alternative.

## Prerequisite

```bash
pip install codegraphx
```

The CLI must be on `PATH`, or set `cliPath` in the plugin's configuration to its
full path.

## Install

DSH Desktop manages its profile itself, so installation has two parts.

**1. Make the package a real dependency of the profile.** Copy this directory
somewhere stable, then from the profile directory:

```powershell
cd $env:DSH_PROFILE_DIR
# add to package.json dependencies:
#   "dsh-codegraph": "file:D:/path/to/this/directory"
node <pnpm.mjs> install
```

**2. Declare the plugin row.** In `$env:DSH_PROFILE_DIR/cordis.patch.yml`:

```yaml
- id: dsh-codegraph
  name: dsh-codegraph
  config:
    cliPath: "D:/path/to/codegraph.exe"
    timeoutMs: 120000
```

Restart DSH.

## Why the install is awkward

Four things about DSH plugin loading cost real time to discover; they are recorded
here so the next person does not repeat it.

**A package in `node_modules` is not an installed package.** Copying a directory
there does nothing. The Loader resolves a row's `name` against the profile's
dependency tree, so the package must be in `dependencies` and installed by pnpm.
`pnpm install --force` will not refresh a `file:` dependency whose source changed —
delete `node_modules/<name>` first.

**The bundle patch and the profile patch must not declare the same id.** This plugin
ships `cordis.patch.yml` with `dsh.bundle.patch` in `package.json`, which the Loader
reads as a bundle. Declaring the same `- id:` in the profile's own patch as well
produces a conflict, and the row silently disappears. Use one or the other.

**`Config` must be a schemastery schema.** A plain object throws
`Cannot read properties of undefined (reading 'validate')` at activation.

**`apply` must be synchronous.** An `await` inside it can land the registration after
the registry has settled the context it needs.

## Why the tools register twice

`apply` registers the tools globally **and** on each agent's own scope, through an
`agent/created` listener:

```js
ctx.on('agent/created', ({ agent }) => {
  for (const tool of buildTools()) agent.ctx.tools.register(tool)
})
```

A global registration reaches agents whose tool list comes from the deployment. But
an agent preset (`~/.dsh/.agent-presets/<name>/agent.cordis.yml`) declares its own
tool rows — `tool-bash`, `tool-fs`, and so on — and an agent built from a preset
resolves tools against its own scope chain, where a global-only registration stays
invisible. The per-agent listener covers presets without editing any preset file,
which is what makes this portable.

Set `registerPerAgent: false` to turn the second registration off.

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `cliPath` | `codegraph` | Executable name or absolute path of the CLI. |
| `timeoutMs` | `120000` | How long one CLI call may run. |
| `registerPerAgent` | `true` | Also register on each agent's scope, for preset-based agents. |

## Limitations

- **A record exists only if the project wrote one.** CodeGraph never invents a reason.
  When a project recorded none, `codegraph_why` reports `found: false`.
- **Not every line is reachable.** Measured across seven real repositories, 12–40% of
  sampled locations returned a line-level card. A changelog decision links to one
  specific line, not to every line it influenced; the file-level fallback covers part
  of the gap.
- **Shallow clones carry only recent history**, so older decisions will not be found.
  `depth` controls how far back indexing reads.
- **A root-level file gets no directory fallback.** The repository root is not a
  subject area, so `why LICENSE:1` reports no record rather than returning every
  root-level decision.

## Verifying an install

The plugin appends one line per activation step to
`%TEMP%\codegraph-plugin-load.log` (or `$TMPDIR`):

```
module-evaluated
apply-entered
define-tool-loaded
global-tools-registered
tools-registered
agent-tools-registered
```

A missing file means the module was never imported — a resolution problem, not a
logic problem. `tools-registered` without `agent-tools-registered` means the agent
event never fired. This distinction is otherwise invisible: a plugin can be
installed, listed, report success, and still never run.
