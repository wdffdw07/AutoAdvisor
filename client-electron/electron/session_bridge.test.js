const test = require('node:test')
const assert = require('node:assert/strict')

const {
  buildSurfaceSnapshotMessage,
  buildCheckpointConfirmMessage,
  buildRecoveryRequestMessage,
  buildSessionCompleteMessage,
  toOverlayCommand,
  isManualContinuation,
  SessionBridge
} = require('./session_bridge')

function makeSnapshot () {
  return {
    context: {
      process_name: 'Photoshop.exe',
      window_title: 'Photoshop',
      dpi_scale: 1,
      window_box: [100, 50, 1400, 900]
    },
    image_base64: 'abc123',
    active_surface: {
      hwnd: '100',
      kind: 'main',
      process_name: 'Photoshop.exe',
      window_title: 'Photoshop',
      surface_signature: 'photoshop.exe|main|100|photoshop'
    },
    surface_stack: [
      {
        hwnd: '100',
        kind: 'main',
        process_name: 'Photoshop.exe',
        window_title: 'Photoshop',
        surface_signature: 'photoshop.exe|main|100|photoshop'
      }
    ]
  }
}

test('buildSurfaceSnapshotMessage emits the initial session.start packet with surface metadata', () => {
  const msg = buildSurfaceSnapshotMessage({
    mode: 'start',
    sessionId: 's-1',
    traceId: 't-1',
    goal: 'blur the image',
    snapshot: makeSnapshot()
  })

  assert.equal(msg.event, 'session.start')
  assert.equal(msg.protocol_version, 'v1')
  assert.equal(msg.goal, 'blur the image')
  assert.deepEqual(msg.context.window_box, [100, 50, 1400, 900])
  assert.equal(msg.surface.hwnd, '100')
  assert.equal(msg.surface_stack.length, 1)
})

test('buildSurfaceSnapshotMessage emits observation packets without restarting the session', () => {
  const msg = buildSurfaceSnapshotMessage({
    mode: 'observe',
    sessionId: 's-1',
    traceId: 't-2',
    snapshot: makeSnapshot()
  })

  assert.equal(msg.event, 'context.update')
  assert.equal(msg.trace_id, 't-2')
  assert.equal(msg.surface_stack[0].surface_signature, 'photoshop.exe|main|100|photoshop')
})

test('buildCheckpointConfirmMessage emits an explicit confirm action', () => {
  const msg = buildCheckpointConfirmMessage({
    sessionId: 's-1',
    traceId: 't-3',
    snapshot: makeSnapshot()
  })

  assert.equal(msg.event, 'user.next')
  assert.equal(msg.action, 'confirm_checkpoint')
  assert.equal(msg.surface.hwnd, '100')
})

test('buildRecoveryRequestMessage emits explicit recovery actions', () => {
  const msg = buildRecoveryRequestMessage({
    sessionId: 's-1',
    traceId: 't-4',
    recoveryAction: 'partial_replan',
    snapshot: makeSnapshot()
  })

  assert.equal(msg.event, 'context.update')
  assert.equal(msg.recovery_action, 'partial_replan')
  assert.equal(msg.surface_stack.length, 1)
})

test('buildSessionCompleteMessage emits KB-required fields', () => {
  const msg = buildSessionCompleteMessage({
    sessionId: 's-1',
    traceId: 't-5'
  })

  assert.equal(msg.event, 'session.complete')
  assert.equal(msg.protocol_version, 'v1')
  assert.equal(msg.trace_id, 't-5')
})

test('toOverlayCommand maps guide.highlight to a visible overlay', () => {
  const command = toOverlayCommand({
    event: 'guide.highlight',
    target: { relative_box: [10, 20, 30, 40], confidence: 0.9 },
    tooltip: 'Click here'
  })

  assert.equal(command.visible, true)
  assert.deepEqual(command.relative_box, [10, 20, 30, 40])
  assert.equal(command.tooltip, 'Click here')
})

test('toOverlayCommand hides overlay for non-highlight events', () => {
  const command = toOverlayCommand({
    event: 'guide.wait_manual',
    tooltip: 'Continue when ready'
  })

  assert.equal(command.visible, false)
  assert.equal(command.tooltip, 'Continue when ready')
})

test('isManualContinuation returns true only for manual-next cases', () => {
  assert.equal(isManualContinuation({ event: 'guide.highlight', require_manual_next: true }), true)
  assert.equal(isManualContinuation({ event: 'guide.highlight', require_manual_next: false }), false)
  assert.equal(isManualContinuation({ event: 'guide.wait_manual' }), true)
})

test('SessionBridge reports disconnected status when the socket closes', async () => {
  const statuses = []
  const bridge = new SessionBridge({
    serverUrl: 'ws://example.test/ws',
    sendToCapsule: () => {},
    sendToOverlay: () => {},
    captureSnapshot: async () => makeSnapshot(),
    WebSocketImpl: class FakeSocket {
      constructor () {
        setImmediate(() => this.onclose && this.onclose())
      }

      send () {}
      close () {}
    },
    onStatus: (status) => statuses.push(status)
  })

  await bridge.startSession({ goal: 'blur the image' })
  await new Promise(resolve => setImmediate(resolve))

  assert.deepEqual(statuses, ['reconnecting', 'disconnected'])
})

test('SessionBridge sends checkpoint confirmation before the next observation snapshot', async () => {
  const sent = []

  class FakeSocket {
    constructor () {
      this.readyState = 0
      setImmediate(() => {
        this.readyState = 1
        this.onopen && this.onopen()
      })
    }

    send (payload) {
      sent.push(JSON.parse(payload))
    }

    close () {}
  }

  const bridge = new SessionBridge({
    serverUrl: 'ws://example.test/ws',
    sendToCapsule: () => {},
    sendToOverlay: () => {},
    captureSnapshot: async () => makeSnapshot(),
    WebSocketImpl: FakeSocket,
    onStatus: () => {}
  })

  await bridge.startSession({ goal: 'blur the image' })
  await new Promise(resolve => setImmediate(resolve))
  bridge.lastGuideEvent = { event: 'guide.highlight', require_manual_next: true }

  await bridge.continueSession()

  assert.equal(sent[0].event, 'session.start')
  assert.equal(sent[1].event, 'user.next')
  assert.equal(sent[1].action, 'confirm_checkpoint')
  assert.equal(sent[2].event, 'context.update')
  assert.equal(sent[2].surface_stack.length, 1)
})

test('SessionBridge can send explicit recovery requests with surface-aware snapshots', async () => {
  const sent = []

  class FakeSocket {
    constructor () {
      this.readyState = 0
      setImmediate(() => {
        this.readyState = 1
        this.onopen && this.onopen()
      })
    }

    send (payload) {
      sent.push(JSON.parse(payload))
    }

    close () {}
  }

  const bridge = new SessionBridge({
    serverUrl: 'ws://example.test/ws',
    sendToCapsule: () => {},
    sendToOverlay: () => {},
    captureSnapshot: async () => makeSnapshot(),
    WebSocketImpl: FakeSocket,
    onStatus: () => {}
  })

  await bridge.startSession({ goal: 'blur the image' })
  await new Promise(resolve => setImmediate(resolve))
  await bridge.requestRecovery({ recoveryAction: 'full_replan' })

  assert.equal(sent.at(-1).event, 'context.update')
  assert.equal(sent.at(-1).recovery_action, 'full_replan')
  assert.equal(sent.at(-1).surface.hwnd, '100')
})

test('buildSurfaceSnapshotMessage preserves cross-window surface stacks for picker flows', () => {
  const msg = buildSurfaceSnapshotMessage({
    mode: 'observe',
    sessionId: 's-1',
    traceId: 't-6',
    snapshot: {
      context: {
        process_name: 'explorer.exe',
        window_title: 'Open',
        dpi_scale: 1,
        window_box: [200, 120, 900, 700]
      },
      image_base64: 'picker123',
      active_surface: {
        hwnd: '300',
        kind: 'picker',
        process_name: 'explorer.exe',
        window_title: 'Open',
        surface_signature: 'explorer.exe|picker|300|open'
      },
      surface_stack: [
        {
          hwnd: '100',
          kind: 'main',
          process_name: 'JianyingPro.exe',
          window_title: 'Jianying',
          surface_signature: 'jianyingpro.exe|main|100|jianying'
        },
        {
          hwnd: '200',
          kind: 'dialog',
          process_name: 'JianyingPro.exe',
          window_title: 'Export dialog',
          surface_signature: 'jianyingpro.exe|dialog|200|export+dialog'
        },
        {
          hwnd: '300',
          kind: 'picker',
          process_name: 'explorer.exe',
          window_title: 'Open',
          surface_signature: 'explorer.exe|picker|300|open'
        }
      ]
    }
  })

  assert.equal(msg.surface_stack.length, 3)
  assert.equal(msg.surface_stack[0].kind, 'main')
  assert.equal(msg.surface_stack[2].kind, 'picker')
  assert.equal(msg.surface.hwnd, '300')
})
