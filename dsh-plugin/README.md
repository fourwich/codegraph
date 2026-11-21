# CodeGraph for DeepSeek Harness

A DSH plugin that puts "why is this line written this way?" where you already are.
Four ways in, from most to least direct:

| Entry | When |
|---|---|
| **Right-click a code block** | The code is on screen. Opens a menu with "Ask why this code is written this way". |
| **`/why` in the composer** | The line is not on screen yet; inserts a `path:line` template. |
| `codegraph_why` tool | The agent decides to check before editing unfamiliar code. |
| A prompt section | Tells the agent that asking is expected, so the tool is not left unused. |

The last two are backed by the [codegraph](https://pypi.org/project/codegraphx/) CLI:

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
`agent/created` listener.

The second registration is not `agent.ctx.tools.register()`. That call looks
agent-local and is not: `ToolRuntime.register()` runs
`this.layers.effect(this.ctx, …)`, reading the scope from the **service's own**
context, and `ScopedLayers.effect` treats an untagged context as the global layer.
`agent.ctx` carries no scope tag, so the tool lands in the global layer either way.

Reaching one agent needs a context tagged with that agent, which
`createScope(agent.ctx, agent)` produces:

```js
const { createScope } = require('@deepseek-ai/dsh-scope')

ctx.on('agent/created', ({ agent }) => {
  const scope = createScope(agent.ctx, agent)   // tagged with this agent
  for (const tool of buildTools()) scope.ctx.tools.register(tool)
  // keep scope.dispose for teardown
})
```

A global registration covers agents whose tool list comes from the deployment. A
preset agent (`~/.dsh/.agent-presets/<name>/agent.cordis.yml`) declares its own tool
rows — `tool-bash`, `tool-fs`, … — and resolves tools against its own scope chain,
where a global-only registration stays invisible. The tagged registration covers
presets without editing any preset file, which is what makes this portable.

Set `registerPerAgent: false` to turn the second registration off.

The activation log records which path ran:

```
agent-tools-registered id=session-… scoped=yes visible=codegraph_why,codegraph_index
```

`scoped=yes` means a tagged context was used. `scoped=no` means the scope package was
unavailable and the registration fell back to global.

## The client half

`client.js` adds two composer affordances, and is **not** an ES module. The browser
loads it through a factory that injects `require`, so a static `import react from
'react'` fails at runtime — the host supplies React, not `node_modules`:

```js
window.__ModuleLoader__.load({
  id: `dsh-codegraph`,
  factory: require => {
    const react = require('react')
    exports.apply = apply
    exports.inject = inject
    return module.exports
  },
})
```

**A right-click entry on every code block.** The `conversation.chat.markdown.fence`
slot is declared `kind: 'hoc'`, so a contribution receives the default renderer as
`children` and wraps it. Wrapping rather than re-implementing keeps syntax
highlighting and streaming behaviour intact. The wrapper reads `useContextMenu` from
the slot props and spreads `getTriggerProps(target)` onto a `div`.

**A `/why` slash entry** for a line that is not on screen, via
`inputTriggers.registerSource`.

### The menu kind is new, and that is allowed

DSH ships `file`, `image`, `directory`, `url`, `workspace`, and `tab` — no `code` or
`selection`. A menu target kind is a plain string: the registry publishes a kind
automatically when the first provider registers for it, so the wrapper and its rows
agree on `codegraph-code` without a separate declaration step.

### What could not be done

Selecting text inside a code block and asking about that selection has no extension
point in this DSH version. The fence slot exposes the fence's `code` and `lang`, not
the user's selection, so the entry acts on the whole block. That is a limitation of
the host, not of this plugin.

### Verifying the client half without a browser

A browser module cannot write files, so the Host `%TEMP%` trace cannot see it.
Instead `apply()` sets a DOM marker, readable in DevTools:

```js
document.documentElement.dataset.codegraph           // "applied"
document.documentElement.dataset.codegraphServices   // "contextMenus,inputTriggers,slots"
```

`undefined` means the bundle never ran — a `dsh.client` or linking problem, not a
logic problem.

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
