/**
 * CodeGraph tools for DeepSeek Harness.
 *
 * CodeGraph answers "why is this line here?" by linking a source line to the
 * decision record that explains it — an ADR, a changelog entry, or a commit body
 * that states a reason. This plugin exposes that lookup to the agent as two tools:
 * index a repository, and ask why a location exists.
 *
 * Every card comes from running the installed `codegraph` CLI. The plugin adds no
 * interpretation of its own, and reports "no record" rather than guessing when a
 * project wrote nothing down.
 *
 * @module dsh-codegraph
 */

import { execFile } from 'node:child_process'
import { appendFileSync, existsSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { promisify } from 'node:util'
import z from '@deepseek-ai/schemastery'

const run = promisify(execFile)

/** This module's own require, for resolving peer packages synchronously. */
const selfRequire = createRequire(import.meta.url)

/**
 * Activation trace.
 *
 * A plugin can be installed, listed, and report success while its module is never
 * evaluated, and "loaded but inactive" looks identical from the outside. These
 * markers make the difference observable. Four writes at startup, and a failure to
 * write is ignored.
 */
const TRACE = join(process.env.TEMP || '.', 'codegraph-plugin-load.log')

function trace(step) {
  try {
    mkdirSync(dirname(TRACE), { recursive: true })
    appendFileSync(TRACE, `${new Date().toISOString()} ${step}\n`)
  } catch {
    // Never let diagnostics break activation.
  }
}

trace('module-evaluated')

export const name = 'codegraph'

/**
 * Services this plugin needs.
 *
 * `agents` carries the `agent/created` event used for per-agent registration; `tools`
 * is the registry itself. Declaring both keeps the plugin inactive in a deployment
 * that has neither, instead of throwing.
 */
export const inject = ['tools', 'agents', 'systemPrompt']

/**
 * Tunable values live in the row's `config` so a user can change them.
 *
 * This must be a schemastery schema: the Loader validates the row's config before
 * calling `apply`, and a plain object throws
 * `Cannot read properties of undefined (reading 'validate')`.
 */
export const Config = z.object({
  cliPath: z.string().default('codegraph').description(
    'Executable or command name that resolves to the codegraph CLI.',
  ),
  timeoutMs: z.number().default(120000).description(
    'How long one CLI invocation may run before it is killed.',
  ),
  registerPerAgent: z.boolean().default(true).description(
    'Also register the tools on each agent\'s own scope, so agent presets see them.',
  ),
})

/**
 * Resolve `defineTool` synchronously.
 *
 * `@deepseek-ai/dsh-tools` is a peer the Loader provides from the Harness
 * installation, so it is located through `createRequire` rather than imported at
 * module scope. `require` is synchronous, which keeps `apply` synchronous too.
 */
function resolveDefineTool() {
  const anchor = process.env.DSH_INSTALL_DIR || process.cwd()
  const anchorRequire = createRequire(`${anchor}/package.json`)
  const entry = anchorRequire.resolve('@deepseek-ai/dsh-tools')
  return selfRequire(entry).defineTool
}

/**
 * Run the CLI and return stdout.
 *
 * `codegraph why` exits 1 when it has no record. That is an answer, not a failure,
 * so exit 1 returns the output instead of throwing.
 */
async function callCli(cliPath, args, timeoutMs, cwd) {
  try {
    const { stdout } = await run(cliPath, args, {
      cwd,
      timeout: timeoutMs,
      maxBuffer: 8 * 1024 * 1024,
      windowsHide: true,
    })
    return stdout
  } catch (error) {
    if (error.code === 1) return error.stdout ?? ''

    const detail = (error.stderr || error.stdout || error.message || '').trim()
    const missing =
      error.code === 'ENOENT'
      || /spawn .* ENOENT/i.test(detail)
      || detail.includes('not recognized')
      || detail.includes('not found')
    if (missing) {
      throw new Error(
        `codegraph CLI not found (tried \`${cliPath}\`). `
        + 'Install it with `pip install codegraphx`, or set this plugin\'s `cliPath` '
        + 'to the executable\'s full path.',
      )
    }
    if (error.killed) {
      throw new Error(
        `codegraph did not finish within ${timeoutMs} ms; raise the plugin's timeoutMs.`,
      )
    }
    throw new Error(detail.slice(0, 800))
  }
}

function parseJson(text) {
  const trimmed = (text ?? '').trim()
  if (!trimmed) return null
  const start = trimmed.indexOf('{')
  if (start < 0) return null
  try {
    return JSON.parse(trimmed.slice(start))
  } catch {
    return null
  }
}

/** One decision reduced to what a reader needs to judge it. */
function summarizeDecision(decision) {
  return {
    content: decision.content ?? '',
    reason: decision.reason ?? '',
    alternatives: Array.isArray(decision.alternatives) ? decision.alternatives : [],
    status: decision.status ?? '',
    source: decision.source ?? '',
    sourceRef: decision.source_ref ?? '',
    date: (decision.timestamp ?? '').slice(0, 10),
    tier: decision.tier ?? '',
  }
}

/**
 * Resolve `@deepseek-ai/dsh-scope`, which provides `createScope`.
 *
 * Registering a tool needs a context that carries a scope tag, and `agent.ctx` has
 * none: `scopeOf(agent.ctx)` returns `undefined`, which `ScopedLayers.effect` reads
 * as "global". That is why a plain `agent.ctx.tools.register()` lands in the global
 * layer and stays invisible to a preset-based agent. `createScope(agent.ctx, agent)`
 * returns a context tagged with that agent as its scope key.
 */
function resolveScopeTools() {
  const anchor = process.env.DSH_INSTALL_DIR || process.cwd()
  const anchorRequire = createRequire(`${anchor}/package.json`)
  let entry
  try {
    entry = anchorRequire.resolve('@deepseek-ai/dsh-scope')
  } catch {
    return undefined
  }
  return selfRequire(entry)
}

/**
 * Build a context whose scope tag is `key`, or fall back to `ctx` itself.
 *
 * The fallback keeps the plugin working on a deployment that lacks the scope
 * package: registration still succeeds, it just stays global.
 */
function scopeFor(ctx, key, scopeTools) {
  if (scopeTools?.createScope === undefined) return { ctx, dispose: undefined }
  const created = scopeTools.createScope(ctx, key)
  return { ctx: created.ctx, dispose: created.dispose }
}

/**
 * Register the CodeGraph tools.
 *
 * A note on why this is more than one `register()` call.
 *
 * `ToolRuntime.register()` runs `this.layers.effect(this.ctx, …)`: it reads the
 * scope from the **service's own** context, not from the caller, so calling it
 * through `agent.ctx.tools` still registers globally. Reaching a single agent needs
 * a context whose scope tag is that agent, which `createScope` produces.
 *
 * Registering globally as well is deliberate: an agent whose tool list comes from
 * the deployment sees the global layer, and a preset agent sees its own.
 *
 * @param ctx - registrant context carrying the tool registry and agent events.
 * @param config - the row's configuration, validated against {@link Config}.
 */
export function apply(ctx, config) {
  trace('apply-entered')
  const defineTool = resolveDefineTool()
  const scopeTools = resolveScopeTools()
  trace(`define-tool-loaded scope=${scopeTools ? 'available' : 'absent'}`)

  const cliPath = config?.cliPath ?? 'codegraph'
  const timeoutMs = config?.timeoutMs ?? 120000
  const registerPerAgent = config?.registerPerAgent !== false
  const build = () => buildToolDefinitions(defineTool, cliPath, timeoutMs)

  // 1. Global registration.
  for (const tool of build()) ctx.tools.register(tool)
  trace('global-tools-registered')

  // 2. Per-agent registration, in that agent's own scope.
  if (registerPerAgent) {
    /** Scope disposers by agent, so unload and disposal both clean up. */
    const byAgent = new Map()

    ctx.effect(() => {
      const offCreated = ctx.on('agent/created', ({ agent }) => {
        if (!agent?.ctx || byAgent.has(agent)) return
        const agentId = agent.id ?? agent.session?.id ?? '(unknown)'

        // The tagged context is what makes the registration agent-local.
        const scope = scopeFor(agent.ctx, agent, scopeTools)
        const disposers = []
        try {
          for (const tool of build()) disposers.push(scope.ctx.tools.register(tool))
        } catch (error) {
          trace(`agent-register-failed ${agentId} ${error?.code ?? error?.message ?? error}`)
          return
        }
        byAgent.set(agent, { disposers, disposeScope: scope.dispose })

        // Report what this agent's own view holds after registering. A successful
        // register is not the same as a visible tool, and that difference is
        // invisible from outside.
        let visible = '(unavailable)'
        try {
          const view = scope.ctx.tools.view?.(agent)
          visible = view?.visible
            ? [...view.visible.keys()].filter((n) => n.startsWith('codegraph_')).join(',') || '(none)'
            : '(no view)'
        } catch (error) {
          visible = `(view threw: ${error?.message ?? error})`
        }
        trace(`agent-tools-registered id=${agentId} scoped=${scopeTools ? 'yes' : 'no'} visible=${visible}`)
      })

      const offDisposed = ctx.on('agent/disposed', ({ agent }) => {
        const entry = byAgent.get(agent)
        if (!entry) return
        for (const dispose of entry.disposers) {
          try {
            dispose()
          } catch {
            // Already removed with the agent scope.
          }
        }
        try {
          entry.disposeScope?.()
        } catch {
          // Scope already gone.
        }
        byAgent.delete(agent)
      })

      return () => {
        offCreated()
        offDisposed()
        for (const entry of byAgent.values()) {
          for (const dispose of entry.disposers) {
            try {
              dispose()
            } catch {
              // Already removed.
            }
          }
          try {
            entry.disposeScope?.()
          } catch {
            // Scope already gone.
          }
        }
        byAgent.clear()
      }
    })
  } else {
    trace('per-agent-disabled')
  }

  trace('tools-registered')

  // Tell the agent when to reach for the tool. Without this the tool exists but a
  // model has no reason to prefer it over reading the code and guessing, which is
  // the behaviour the whole project exists to replace.
  try {
    ctx.systemPrompt?.section({
      name: 'codegraph:why-hint',
      order: 60,
      text:
        'When the user asks why a line of code is written a certain way — rather than '
        + 'what it does — call `codegraph_why` with `path:line` instead of inferring from '
        + 'the code. It returns the decision the project recorded (an ADR, a changelog '
        + 'entry, or a commit message stating a reason), or found:false when the project '
        + 'wrote nothing down. Report found:false as an answer; never invent a rationale. '
        + 'Index the repository with `codegraph_index` first if the tool reports no database.',
    })
    trace('prompt-section-registered')
  } catch (error) {
    trace(`prompt-section-failed ${error?.message ?? error}`)
  }
}

/** Build both tool definitions; each registration gets its own instance. */
function buildToolDefinitions(defineTool, cliPath, timeoutMs) {
  return [
    buildWhyTool(defineTool, cliPath, timeoutMs),
    buildIndexTool(defineTool, cliPath, timeoutMs),
  ]
}

function buildWhyTool(defineTool, cliPath, timeoutMs) {
  return defineTool({
    name: 'codegraph_why',
    description:
      'Explain why a line of code exists, from the repository\'s own decision records: ADRs, changelog entries, and commit messages that state a reason or a rejected alternative. '
      + 'Returns the decision bound to that line, or the decisions governing the file when nothing is bound to the exact line. '
      + 'Use it before changing unfamiliar code, and prefer it over inferring intent from the code alone. '
      + 'Returns found=false when the project recorded no rationale — that is the honest answer, not a failure. '
      + 'The repository must be indexed first with codegraph_index.',
    parameters: {
      location: {
        type: 'string',
        required: true,
        description: 'A location as `path:line`, absolute or relative to the repository root. Example: `src/app.py:42`.',
      },
      root: {
        type: 'string',
        description: 'Repository root to search. Defaults to the working directory; the database is found by walking up from it.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          found: { type: 'boolean', required: true },
          binding: { type: 'string', required: true },
          node: {
            type: 'object',
            additionalProperties: false,
            properties: {
              name: { type: 'string', required: true },
              kind: { type: 'string', required: true },
              file: { type: 'string', required: true },
              start: { type: 'integer', required: true },
              end: { type: 'integer', required: true },
            },
          },
          decisions: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                content: { type: 'string', required: true },
                reason: { type: 'string', required: true },
                alternatives: { type: 'array', required: true, items: { type: 'string' } },
                status: { type: 'string', required: true },
                source: { type: 'string', required: true },
                sourceRef: { type: 'string', required: true },
                date: { type: 'string', required: true },
                tier: { type: 'string', required: true },
              },
            },
          },
        },
      },
      render: (_args, value) => {
        const lines = []
        if (value.node) {
          lines.push(
            `${value.node.kind} ${value.node.name} — ${value.node.file}:${value.node.start}-${value.node.end}`,
          )
        }
        if (!value.found) {
          lines.push('No decision record for this location — the project wrote down no rationale here.')
        } else {
          if (value.binding === 'file' || value.binding === 'dir') {
            lines.push('Nothing is bound to this exact line; these govern the area:')
          }
          value.decisions.slice(0, 3).forEach((decision, index) => {
            lines.push(`${index + 1}. ${decision.content}`)
            if (decision.reason) lines.push(`   reason: ${decision.reason}`)
            if (decision.alternatives.length) {
              lines.push(`   rejected: ${decision.alternatives.join(' | ')}`)
            }
          })
        }
        return [{ type: 'text', text: lines.join('\n') }]
      },
    },
    presentCall: (args) => ({
      card: 'generic',
      title: 'Why this line exists',
      kind: 'read',
      rawInput: { location: args.location },
    }),
    async execute(args) {
      const cwd = args.root && args.root.length > 0 ? args.root : process.cwd()
      const out = await callCli(cliPath, ['why', args.location, '--json'], timeoutMs, cwd)
      const payload = parseJson(out)
      if (payload === null) {
        throw new Error(
          'codegraph why returned no JSON. Index the repository first with codegraph_index.',
        )
      }
      const bound = payload.decisions ?? []
      const related = payload.related ?? []
      const chosen = bound.length > 0 ? bound : related
      const node = payload.node
      return {
        found: chosen.length > 0,
        binding: payload.binding ?? 'none',
        ...(node
          ? {
              node: {
                name: node.name,
                kind: node.kind,
                file: node.file_path,
                start: node.line_start,
                end: node.line_end,
              },
            }
          : {}),
        decisions: chosen.slice(0, 5).map(summarizeDecision),
      }
    },
  })
}

function buildIndexTool(defineTool, cliPath, timeoutMs) {
  return defineTool({
    name: 'codegraph_index',
    description:
      'Index a repository so codegraph_why can answer questions about it. '
      + 'Parses the code with tree-sitter, walks the git history, and extracts decision records into `<root>/.codegraph/graph.db`. '
      + 'Run it once per repository before asking why. Takes a few seconds per hundred commits.',
    parameters: {
      root: {
        type: 'string',
        required: true,
        description: 'Repository root to index.',
      },
      depth: {
        type: 'integer',
        description: 'How many commits of history to read. Deeper history finds older decisions and takes longer. Defaults to 50.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          nodes: { type: 'integer', required: true },
          edges: { type: 'integer', required: true },
          decisions: { type: 'integer', required: true },
          database: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: `Indexed: ${value.nodes} nodes, ${value.edges} edges, ${value.decisions} decision records.`,
      }],
    },
    presentCall: (args) => ({
      card: 'generic',
      title: 'Index a repository',
      kind: 'other',
      rawInput: { root: args.root, depth: args.depth },
    }),
    async execute(args) {
      const depth = args.depth ?? 50
      const out = await callCli(
        cliPath,
        ['index', args.root, '--depth', String(depth), '--json'],
        timeoutMs,
        args.root,
      )
      const payload = parseJson(out)
      if (payload === null) {
        throw new Error('codegraph index returned no JSON; check that the CLI ran successfully.')
      }
      return {
        nodes: payload.nodes ?? 0,
        edges: payload.edges ?? 0,
        decisions: payload.decisions ?? 0,
        database: join(args.root, '.codegraph', 'graph.db'),
      }
    },
  })
}
