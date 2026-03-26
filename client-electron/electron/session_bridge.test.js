const test = require('node:test')
const assert = require('node:assert/strict')

const {
  buildSessionStartMessage,
  buildContextUpdateMessage,
  toOverlayCommand,
  isManualContinuation
} = require('./session_bridge')

test('buildSessionStartMessage emits KB-required fields', () => {
  const msg = buildSessionStartMessage({
    sessionId: 's-1',
    traceId: 't-1',
    goal: 'blur the image',
    context: {
      process_name: 'Photoshop.exe',
      window_title: 'Photoshop',
      dpi_scale: 1,
      window_box: [100, 50, 1400, 900]
    },
    image_base64: 'abc123'
  })

  assert.equal(msg.event, 'session.start')
  assert.equal(msg.protocol_version, 'v1')
  assert.equal(msg.goal, 'blur the image')
  assert.deepEqual(msg.context.window_box, [100, 50, 1400, 900])
})

test('buildContextUpdateMessage emits KB-required fields', () => {
  const msg = buildContextUpdateMessage({
    sessionId: 's-1',
    traceId: 't-2',
    context: {
      process_name: 'Photoshop.exe',
      window_title: 'Photoshop',
      dpi_scale: 1,
      window_box: [100, 50, 1400, 900]
    },
    image_base64: 'abc123'
  })

  assert.equal(msg.event, 'context.update')
  assert.equal(msg.protocol_version, 'v1')
  assert.equal(msg.trace_id, 't-2')
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
