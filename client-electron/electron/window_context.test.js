const test = require('node:test')
const assert = require('node:assert/strict')

const {
  chooseWindowContext,
  enrichWindowContext,
  isSelfWindowContext
} = require('./window_context')

test('isSelfWindowContext matches Electron process names case-insensitively', () => {
  assert.equal(
    isSelfWindowContext(
      { process_name: 'Electron.EXE', window_box: [10, 20, 300, 200] },
      { selfProcessNames: new Set(['electron.exe']) }
    ),
    true
  )
})

test('chooseWindowContext prefers a non-self preferred context', () => {
  const chosen = chooseWindowContext({
    preferredContext: {
      process_name: 'Photoshop.exe',
      window_title: 'Photoshop',
      window_box: [100, 50, 1400, 900],
      dpi_scale: 1
    },
    fallbackContext: {
      process_name: 'electron.exe',
      window_title: 'Capsule',
      window_box: [20, 120, 340, 520],
      dpi_scale: 1
    },
    lastContext: {
      process_name: 'CapCut.exe',
      window_title: 'CapCut',
      window_box: [0, 0, 1600, 900],
      dpi_scale: 1
    },
    selfProcessNames: new Set(['electron.exe'])
  })

  assert.equal(chosen.process_name, 'Photoshop.exe')
})

test('chooseWindowContext falls back to the last non-self context when current candidates are self windows', () => {
  const chosen = chooseWindowContext({
    preferredContext: {
      process_name: 'electron.exe',
      window_title: 'Capsule',
      window_box: [20, 120, 340, 520],
      dpi_scale: 1
    },
    fallbackContext: {
      process_name: 'electron.exe',
      window_title: 'Overlay',
      window_box: [0, 0, 1920, 1080],
      dpi_scale: 1
    },
    lastContext: {
      process_name: 'CapCut.exe',
      window_title: 'CapCut',
      window_box: [100, 50, 1600, 900],
      dpi_scale: 1
    },
    selfProcessNames: new Set(['electron.exe'])
  })

  assert.equal(chosen.process_name, 'CapCut.exe')
})

test('chooseWindowContext returns null when every candidate points at the Electron process', () => {
  const chosen = chooseWindowContext({
    preferredContext: {
      process_name: 'electron.exe',
      window_title: 'Capsule',
      window_box: [20, 120, 340, 520],
      dpi_scale: 1
    },
    fallbackContext: {
      process_name: 'electron.exe',
      window_title: 'Overlay',
      window_box: [0, 0, 1920, 1080],
      dpi_scale: 1
    },
    lastContext: {
      process_name: 'electron.exe',
      window_title: 'Capsule',
      window_box: [20, 120, 340, 520],
      dpi_scale: 1
    },
    selfProcessNames: new Set(['electron.exe'])
  })

  assert.equal(chosen, null)
})

test('chooseWindowContext ignores Codex windows by default and reuses the last real target', () => {
  const chosen = chooseWindowContext({
    fallbackContext: {
      process_name: 'Codex.exe',
      window_title: 'Codex',
      window_box: [50, 50, 1200, 800],
      dpi_scale: 1
    },
    lastContext: {
      process_name: 'CapCut.exe',
      window_title: 'CapCut',
      window_box: [100, 50, 1600, 900],
      dpi_scale: 1
    },
    execPath: 'D:\\software\\AutoDirectorCopilot\\project\\client-electron\\node_modules\\electron\\dist\\electron.exe'
  })

  assert.equal(chosen.process_name, 'CapCut.exe')
})

test('enrichWindowContext adds surface metadata that is safe to serialize', () => {
  const enriched = enrichWindowContext({
    hwnd: '500',
    owner_hwnd: '300',
    process_name: 'explorer.exe',
    window_title: 'Save As',
    window_box: [100, 50, 800, 600],
    dpi_scale: 1
  })

  assert.equal(enriched.kind, 'picker')
  assert.deepEqual(enriched.title_keywords, ['save', 'as'])
  assert.ok(enriched.surface_signature)
})
