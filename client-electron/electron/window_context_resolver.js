'use strict'

const {
  chooseWindowContext,
  isUsableWindowContext
} = require('./window_context')

async function resolveWindowContext ({
  preferredContext,
  getActiveWindow,
  retryGetActiveWindow,
  probeWindowAtCursor,
  lastContext,
  selfProcessNames,
  rememberContext = () => {}
} = {}) {
  const options = { selfProcessNames }

  if (isUsableWindowContext(preferredContext, options)) {
    rememberContext(preferredContext)
    return preferredContext
  }

  const fallbackContext = typeof getActiveWindow === 'function'
    ? await getActiveWindow()
    : null

  let retryContext = null
  let cursorContext = null
  const hasReusableLastContext = isUsableWindowContext(lastContext, options)

  if (!hasReusableLastContext &&
      !isUsableWindowContext(fallbackContext, options) &&
      typeof retryGetActiveWindow === 'function') {
    retryContext = await retryGetActiveWindow(fallbackContext)
  }

  if (!isUsableWindowContext(retryContext || fallbackContext, options) &&
      typeof probeWindowAtCursor === 'function') {
    cursorContext = await probeWindowAtCursor(retryContext || fallbackContext)
  }

  const targetContext = chooseWindowContext({
    preferredContext,
    fallbackContext: cursorContext || retryContext || fallbackContext,
    lastContext,
    selfProcessNames
  })

  rememberContext(targetContext)
  return targetContext
}

module.exports = {
  resolveWindowContext
}
