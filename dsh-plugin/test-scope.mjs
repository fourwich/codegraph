/**
 * Why per-agent tool registration needs `createScope`.
 *
 * `ToolRuntime.register()` runs `this.layers.effect(this.ctx, …)`, which reads the
 * scope from the **service's own** context. Calling `agent.ctx.tools.register()`
 * therefore registers globally, however agent-local the call looks: `agent.ctx`
 * carries no scope tag, and an untagged context means the global layer.
 *
 * `createScope(agent.ctx, agent)` returns a context tagged with that agent, which is
 * what makes the registration land in that agent's layer.
 *
 * This asserts the tag, which is the property the plugin depends on. The plugin's own
 * registration path is covered by `test-client.mjs` and by the `scoped=` field in the
 * Host activation log.
 */

import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const anchorRequire = createRequire(`${process.env.DSH_INSTALL_DIR}/package.json`)
const scopeEntry = anchorRequire.resolve('@deepseek-ai/dsh-scope')
const { createScope, scopeOf } = await import(pathToFileURL(scopeEntry).href)

console.log('  createScope:', typeof createScope)
console.log('  scopeOf    :', typeof scopeOf)

if (typeof createScope !== 'function' || typeof scopeOf !== 'function') {
  console.error('  FAIL: dsh-scope does not export what the plugin uses')
  process.exit(1)
}

// A minimal Cordis-shaped context: `createScope` uses `ctx.plugin` to mount the
// scope fiber and reads `.ctx` off the result.
function makeCtx() {
  const ctx = {
    plugin: () => ({ ctx, dispose: () => {} }),
    extend: (extra) => Object.assign(Object.create(ctx), extra),
    effect: (fn) => fn(),
    on: () => () => {},
  }
  return ctx
}

const agentCtx = makeCtx()
const untagged = scopeOf(agentCtx)
console.log('\n  scopeOf(agent.ctx):', untagged)

if (untagged !== undefined) {
  console.error('  FAIL: a plain agent context is expected to be untagged')
  process.exit(1)
}

const key = { id: 'agent-under-test' }
const scoped = createScope(agentCtx, key)
const tagged = scopeOf(scoped.ctx)

console.log('  scopeOf(createScope(...).ctx):', JSON.stringify(tagged))
console.log('  tagged at all               :', tagged !== undefined)

if (tagged === undefined) {
  console.error('  FAIL: createScope produced an untagged context, so it cannot scope a registration')
  process.exit(1)
}
if (tagged === untagged) {
  console.error('  FAIL: scoped and unscoped contexts are indistinguishable')
  process.exit(1)
}

// A second scope must be distinct, or two agents would share one layer.
const other = createScope(makeCtx(), { id: 'another-agent' })
console.log('  two scopes differ           :', scopeOf(other.ctx) !== tagged)
if (scopeOf(other.ctx) === tagged) {
  console.error('  FAIL: separate createScope calls produced the same scope key')
  process.exit(1)
}

console.log('\n  OK: createScope tags a context, which is what makes a registration agent-local.')
