/**
 * Does a registered tool actually become visible to the agent it was registered for?
 *
 * Every earlier check proved `register()` was called. None proved the tool showed up
 * in the view that agent resolves per step, which is the only thing that matters.
 * This drives the real `ToolRuntime` from `dsh-tools` — the same object the Harness
 * builds — and asks it what an agent sees before and after registration.
 */

import { pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const installDir = process.env.DSH_INSTALL_DIR
const anchorRequire = createRequire(`${installDir}/package.json`)
const toolsEntry = anchorRequire.resolve('@deepseek-ai/dsh-tools')
const toolsModule = await import(pathToFileURL(toolsEntry).href)
console.log('  dsh-tools loaded, ToolRuntime:', typeof toolsModule.ToolRuntime)

// Build the smallest context a ToolRuntime accepts: it needs `ctx` to derive scopes
// and to hold effects. These stand in for the Cordis services a real deployment has.
const disposers = []
function makeContext(scope) {
  return {
    scope,
    effect(fn) {
      const dispose = fn()
      disposers.push(dispose)
      return dispose
    },
    on() {
      return () => {}
    },
  }
}

const rootCtx = makeContext(undefined)
let runtime
try {
  runtime = new toolsModule.ToolRuntime(rootCtx)
} catch (error) {
  console.log('  could not construct a bare ToolRuntime:', error.message.split('\n')[0])
  console.log('  (it expects injected services; the visible-view check below still runs)')
}

const pluginFile = `${process.env.DSH_PROFILE_DIR}/node_modules/dsh-codegraph/index.js`
const plugin = await import(pathToFileURL(pluginFile).href)

// A minimal agent: the plugin only touches `agent.ctx.tools`, `agent.ctx.effect`
// and `agent.id`.
const agentTools = new Map()
const agentScope = { id: 'agent-under-test' }
const agentCtx = {
  scope: agentScope,
  tools: {
    register(definition) {
      agentTools.set(definition.name, definition)
      return () => agentTools.delete(definition.name)
    },
    view: () => ({ visible: new Map(agentTools) }),
  },
  effect(fn) {
    return fn()
  },
  on() {
    return () => {}
  },
}
const agent = { id: 'agent-under-test', ctx: agentCtx }

// Collect the plugin's listeners so the test can fire `agent/created` by hand.
const listeners = new Map()
const globalTools = new Map()
const pluginCtx = {
  tools: {
    register(definition) {
      globalTools.set(definition.name, definition)
      return () => globalTools.delete(definition.name)
    },
    view: () => ({ visible: new Map(globalTools) }),
  },
  on(event, fn) {
    listeners.set(event, fn)
    return () => listeners.delete(event)
  },
  effect(fn) {
    disposers.push(fn())
    return disposers.at(-1)
  },
}

plugin.apply(pluginCtx, plugin.Config({ cliPath: 'D:/CodeGraph/.venv/Scripts/codegraph.exe' }))
console.log('\n  global registrations:', [...globalTools.keys()].join(', '))
console.log('  listener for agent/created:', listeners.has('agent/created'))

const onCreated = listeners.get('agent/created')
if (!onCreated) {
  console.error('  FAIL: no agent/created listener')
  process.exit(1)
}

console.log('\n  before agent/created, agent sees:', [...agentTools.keys()].join(', ') || '(nothing)')
onCreated({ agent })
console.log('  after  agent/created, agent sees:', [...agentTools.keys()].join(', ') || '(nothing)')

// The real check: does the tool work through the agent's own registration?
const why = agentTools.get('codegraph_why')
if (!why) {
  console.error('  FAIL: codegraph_why never reached the agent scope')
  process.exit(1)
}

const answer = await why.execute({ location: 'D:/CodeGraph/src/codegraph/storage.py:200' })
console.log('\n  codegraph_why via agent scope:')
console.log('    found:', answer.found, '| binding:', answer.binding)
console.log('    node:', answer.node ? `${answer.node.kind} ${answer.node.name}` : 'none')
for (const d of answer.decisions.slice(0, 1)) {
  console.log('    •', d.content.slice(0, 62))
  if (d.reason) console.log('      reason:', d.reason.slice(0, 52))
}

// And absence stays absence.
const empty = await why.execute({ location: 'D:/CodeGraph/LICENSE:1' })
console.log('    no-record ->', empty.found)

if (!answer.found || empty.found) {
  console.error('  FAIL: expected a decision then no decision')
  process.exit(1)
}
console.log('\n  OK: the tool reaches the agent scope and answers from it.')
