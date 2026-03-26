'use strict'

function formatWindowCaptureLabel (context) {
  const processName = context && context.process_name ? context.process_name : ''
  return processName ? `检测到: ${processName}` : ''
}

function buildShortcutCaptureFeedback (payload) {
  if (!payload || payload.accelerator !== 'F9') {
    return null
  }

  if (payload.error) {
    return {
      statusState: 'error',
      statusText: '未捕获',
      detailText: '请先切回目标软件，再按 F9'
    }
  }

  if (payload.captured_context && payload.captured_context.process_name) {
    return {
      statusState: 'captured',
      statusText: '已捕获',
      detailText: formatWindowCaptureLabel(payload.captured_context)
    }
  }

  return {
    statusState: 'idle',
    statusText: '空闲',
    detailText: ''
  }
}

const captureFeedbackApi = {
  buildShortcutCaptureFeedback,
  formatWindowCaptureLabel
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = captureFeedbackApi
}

if (typeof window !== 'undefined') {
  window.captureFeedback = captureFeedbackApi
}
