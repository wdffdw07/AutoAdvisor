const test = require('node:test')
const assert = require('node:assert/strict')

const { SurfaceTracker } = require('./surface_tracker')

function surface (overrides = {}) {
  return {
    hwnd: '100',
    owner_hwnd: '',
    kind: 'main',
    process_name: 'ExampleApp.exe',
    window_title: 'Example App',
    window_box: [100, 50, 1280, 800],
    dpi_scale: 1,
    ...overrides
  }
}

test('SurfaceTracker keeps a main -> dialog -> picker stack and pops back to the parent surface', () => {
  const tracker = new SurfaceTracker({ selfProcessNames: new Set(['electron.exe', 'codex.exe']) })

  tracker.update(surface({ hwnd: '100', kind: 'main', window_title: 'Editor' }))
  tracker.update(surface({ hwnd: '101', owner_hwnd: '100', kind: 'dialog', window_title: 'Export dialog' }))
  tracker.update(surface({ hwnd: '102', owner_hwnd: '101', kind: 'picker', process_name: 'explorer.exe', window_title: 'Open' }))

  assert.deepEqual(tracker.snapshot().surface_stack.map((item) => item.hwnd), ['100', '101', '102'])

  tracker.update(surface({ hwnd: '101', owner_hwnd: '100', kind: 'dialog', window_title: 'Export dialog' }))
  assert.deepEqual(tracker.snapshot().surface_stack.map((item) => item.hwnd), ['100', '101'])

  tracker.update(surface({ hwnd: '100', kind: 'main', window_title: 'Editor' }))
  assert.deepEqual(tracker.snapshot().surface_stack.map((item) => item.hwnd), ['100'])
})

test('SurfaceTracker preserves the active surface even when the process stays the same', () => {
  const tracker = new SurfaceTracker({ selfProcessNames: new Set(['electron.exe', 'codex.exe']) })

  tracker.update(surface({ hwnd: '200', kind: 'main', process_name: 'JianyingPro.exe', window_title: 'Jianying' }))
  tracker.update(surface({ hwnd: '201', owner_hwnd: '200', kind: 'dialog', process_name: 'JianyingPro.exe', window_title: 'Preferences' }))

  const snapshot = tracker.snapshot()
  assert.equal(snapshot.active_surface.hwnd, '201')
  assert.deepEqual(snapshot.surface_stack.map((item) => item.hwnd), ['200', '201'])
})

test('SurfaceTracker ignores self surfaces from the capsule and overlay windows', () => {
  const tracker = new SurfaceTracker({ selfProcessNames: new Set(['electron.exe', 'codex.exe']) })

  tracker.update(surface({ hwnd: '300', process_name: 'CapCut.exe', window_title: 'CapCut' }))
  tracker.update(surface({ hwnd: '999', process_name: 'electron.exe', window_title: 'Capsule', kind: 'dialog' }))

  const snapshot = tracker.snapshot()
  assert.equal(snapshot.active_surface.hwnd, '300')
  assert.deepEqual(snapshot.surface_stack.map((item) => item.hwnd), ['300'])
})

test('SurfaceTracker snapshot is serializable and carries a surface stack payload', () => {
  const tracker = new SurfaceTracker({ selfProcessNames: new Set(['electron.exe', 'codex.exe']) })

  tracker.update(surface({
    hwnd: '400',
    owner_hwnd: '399',
    kind: 'picker',
    process_name: 'explorer.exe',
    window_title: 'Save As'
  }))

  const snapshot = tracker.snapshot()
  const serialized = JSON.parse(JSON.stringify(snapshot))

  assert.equal(serialized.active_surface.hwnd, '400')
  assert.deepEqual(serialized.surface_stack[0].title_keywords, ['save', 'as'])
  assert.ok(serialized.surface_stack[0].surface_signature)
})
