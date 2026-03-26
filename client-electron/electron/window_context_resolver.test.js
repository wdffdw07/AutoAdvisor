const test = require('node:test')
const assert = require('node:assert/strict')

const { resolveWindowContext } = require('./window_context_resolver')

test('resolveWindowContext returns the preferred non-self context without sampling again', async () => {
  const context = {
    process_name: 'JianyingPro.exe',
    window_title: 'CapCut',
    window_box: [100, 50, 1600, 900],
    dpi_scale: 1
  }

  const calls = []
  const resolved = await resolveWindowContext({
    preferredContext: context,
    getActiveWindow: async () => {
      calls.push('getActiveWindow')
      return null
    },
    retryGetActiveWindow: async () => {
      calls.push('retryGetActiveWindow')
      return null
    },
    selfProcessNames: new Set(['electron.exe', 'codex.exe'])
  })

  assert.equal(resolved, context)
  assert.deepEqual(calls, [])
})

test('resolveWindowContext retries in the background when the first sample is the control surface itself', async () => {
  const calls = []

  const resolved = await resolveWindowContext({
    getActiveWindow: async () => {
      calls.push('getActiveWindow')
      return {
        process_name: 'electron.exe',
        window_title: 'Capsule',
        window_box: [20, 120, 340, 520],
        dpi_scale: 1
      }
    },
    retryGetActiveWindow: async () => {
      calls.push('retryGetActiveWindow')
      return {
        process_name: 'JianyingPro.exe',
        window_title: 'CapCut',
        window_box: [100, 50, 1600, 900],
        dpi_scale: 1
      }
    },
    selfProcessNames: new Set(['electron.exe', 'codex.exe'])
  })

  assert.equal(resolved.process_name, 'JianyingPro.exe')
  assert.deepEqual(calls, ['getActiveWindow', 'retryGetActiveWindow'])
})

test('resolveWindowContext reuses the last known target when current samples are all self windows', async () => {
  const resolved = await resolveWindowContext({
    getActiveWindow: async () => ({
      process_name: 'electron.exe',
      window_title: 'Capsule',
      window_box: [20, 120, 340, 520],
      dpi_scale: 1
    }),
    retryGetActiveWindow: async () => ({
      process_name: 'codex.exe',
      window_title: 'Codex',
      window_box: [40, 40, 1200, 800],
      dpi_scale: 1
    }),
    lastContext: {
      process_name: 'msedge.exe',
      window_title: 'Edge',
      window_box: [80, 40, 1700, 960],
      dpi_scale: 1
    },
    selfProcessNames: new Set(['electron.exe', 'codex.exe'])
  })

  assert.equal(resolved.process_name, 'msedge.exe')
})

test('resolveWindowContext falls back to the window under the cursor when foreground samples stay on self windows', async () => {
  const calls = []

  const resolved = await resolveWindowContext({
    getActiveWindow: async () => {
      calls.push('getActiveWindow')
      return {
        process_name: 'electron.exe',
        window_title: 'Capsule',
        window_box: [20, 120, 340, 520],
        dpi_scale: 1
      }
    },
    retryGetActiveWindow: async () => {
      calls.push('retryGetActiveWindow')
      return {
        process_name: 'codex.exe',
        window_title: 'Codex',
        window_box: [40, 40, 1200, 800],
        dpi_scale: 1
      }
    },
    probeWindowAtCursor: async () => {
      calls.push('probeWindowAtCursor')
      return {
        process_name: 'JianyingPro.exe',
        window_title: 'Jianying',
        window_box: [100, 50, 1600, 900],
        dpi_scale: 1
      }
    },
    selfProcessNames: new Set(['electron.exe', 'codex.exe'])
  })

  assert.equal(resolved.process_name, 'JianyingPro.exe')
  assert.deepEqual(calls, ['getActiveWindow', 'retryGetActiveWindow', 'probeWindowAtCursor'])
})
