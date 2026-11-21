/**
 * Load `client.js` the way the browser does, then drive both contributions.
 *
 * The file is a `window.__ModuleLoader__.load({ id, factory })` call, not an ESM
 * module: the client bundle hands `require` to a factory so `react` comes from the
 * host rather than from node_modules. Importing it with `import()` would fail, so
 * this provides a `window` with a loader that runs the factory against stubs.
 */

import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const nodeRequire = createRequire(`${process.env.DSH_PROFILE_DIR}/package.json`)

// A React stand-in that is enough for the wrapper: createElement, useMemo, and
// nothing that needs a reconciler.
const reactStub = {
  createElement: (type, props, ...children) => ({ type, props, children }),
  useMemo: (fn) => fn(),
  // Hooks are inert here: the test calls the component once to check its output
  // shape, not to run a render loop.
  useState: (initial) => [typeof initial === 'function' ? initial() : initial, () => {}],
  useCallback: (fn) => fn,
  useRef: (initial) => ({ current: initial }),
  useEffect: () => {},
}

const LOADED = new Map()

/** Minimal `window.__ModuleLoader__`. */
const loader = {
  load({ id, factory }) {
    const require = (name) => {
      if (name === 'react') return reactStub
      if (name === 'react/jsx-runtime') return { jsx: reactStub.createElement, jsxs: reactStub.createElement }
      throw new Error(`unexpected require(${JSON.stringify(name)})`)
    }
    LOADED.set(id, factory(require))
  },
}

globalThis.window = { __ModuleLoader__: loader }

const file = `${process.env.DSH_PROFILE_DIR}/node_modules/dsh-codegraph/client.js`
const source = readFileSync(file, 'utf8')
// Execute the file body with `window` on the global. It is not a module, so a
// function wrapper is the faithful way to run it.
// eslint-disable-next-line no-new-func
new Function('window', source)(globalThis.window)

console.log('  loaded modules:', [...LOADED.keys()].join(', ') || '(none)')

const client = LOADED.get('dsh-codegraph')
if (client === undefined) {
  console.error('  FAIL: the module never registered')
  process.exit(1)
}
console.log('  exports:', Object.keys(client).sort().join(', '))

if (typeof client.apply !== 'function') {
  console.error('  FAIL: no apply export')
  process.exit(1)
}
if (!Array.isArray(client.inject) || client.inject.length === 0) {
  console.error('  FAIL: inject must list the client packages it orders against')
  process.exit(1)
}
console.log('  inject:', client.inject.length, 'entries')

// --- contributions ---------------------------------------------------------

const fenceRegs = []
const menuRegs = []
const slashSources = new Map()

const ctx = {
  slots: {
    inject: (_name, fn) => {
      fn()
      return () => {}
    },
    register: (desc, component) => {
      fenceRegs.push({ desc, component })
      return () => {}
    },
  },
  get(name) {
    if (name === 'contextMenus') {
      return {
        register(provider) {
          menuRegs.push(provider)
          return () => {}
        },
      }
    }
    if (name === 'inputTriggers') {
      return {
        registerSource(source) {
          slashSources.set(`${source.trigger}${source.name}`, source)
          return () => slashSources.delete(`${source.trigger}${source.name}`)
        },
      }
    }
    return undefined
  },
  effect(fn) {
    return fn()
  },
}

client.apply(ctx)

console.log('\n  fence contributions:', fenceRegs.length)
for (const { desc, component } of fenceRegs) {
  console.log('    name:', desc.name)
  console.log('    id  :', desc.id)
  console.log('    order:', desc.order)
  console.log('    hoc :', typeof component)
}

if (fenceRegs.length !== 1) {
  console.error('  FAIL: expected exactly one fence contribution')
  process.exit(1)
}

// A kind: 'hoc' contribution is a plain component: the renderer calls it with the
// default renderer in children. It must wrap that child, not replace it.
const leaf = { type: 'pre', text: 'a\nb' }
const tree = fenceRegs[0].component({ code: 'a\nb', lang: 'py', children: leaf })
console.log('  hoc wrapper type :', tree?.type)
console.log('  keeps its child  :', Boolean(tree?.children))
const button = tree?.children?.[0]
console.log('  button type      :', button?.type)
console.log('  button label     :', button?.children)

console.log('\n  slash sources:', [...slashSources.keys()].join(', ') || '(none)')
const why = slashSources.get('/why')
if (why === undefined) {
  console.error('  FAIL: /why did not register')
  process.exit(1)
}
const picked = why.onPick({ candidate: { value: '/why' } })
console.log('    onPick ->', JSON.stringify(picked))
if (!picked?.insert?.ref) {
  console.error('  FAIL: onPick must return { insert: { ref } }')
  process.exit(1)
}

// A deployment with neither service must still load without throwing.
try {
  client.apply({ slots: undefined })
  console.log('\n  minimal ctx: ok')
} catch (error) {
  console.error('  FAIL: minimal ctx threw —', error.message)
  process.exit(1)
}

console.log('\n  OK: the client bundle loads and both contributions register.')
