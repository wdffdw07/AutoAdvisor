const test = require('node:test')
const assert = require('node:assert/strict')

const {
  formatWindowCaptureLabel,
  buildShortcutCaptureFeedback
} = require('./capture_feedback')

test('formatWindowCaptureLabel uses the process name when a window is captured', () => {
  assert.equal(
    formatWindowCaptureLabel({ process_name: 'CapCut.exe' }),
    '检测到: CapCut.exe'
  )
})

test('buildShortcutCaptureFeedback reports a visible success state for F9 captures', () => {
  const feedback = buildShortcutCaptureFeedback({
    accelerator: 'F9',
    captured_context: { process_name: 'CapCut.exe' }
  })

  assert.deepEqual(feedback, {
    statusState: 'captured',
    statusText: '已捕获',
    detailText: '检测到: CapCut.exe'
  })
})

test('buildShortcutCaptureFeedback reports an explicit retry hint when no target window was found', () => {
  const feedback = buildShortcutCaptureFeedback({
    accelerator: 'F9',
    error: 'No target window detected. Press F9 while the target app is focused.'
  })

  assert.deepEqual(feedback, {
    statusState: 'error',
    statusText: '未捕获',
    detailText: '请先切回目标软件，再按 F9'
  })
})
