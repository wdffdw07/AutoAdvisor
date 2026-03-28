'use strict'

const {
  chooseWindowContext,
  enrichWindowContext,
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
  const preferred = enrichWindowContext(preferredContext)

  if (isUsableWindowContext(preferred, options)) {
    rememberContext(preferred)
    return preferred
  }

  const fallbackContext = typeof getActiveWindow === 'function'
    ? enrichWindowContext(await getActiveWindow())
    : null

  let retryContext = null
  let cursorContext = null
  const reusableLastContext = enrichWindowContext(lastContext)
  const hasReusableLastContext = isUsableWindowContext(reusableLastContext, options)

  if (!hasReusableLastContext &&
      !isUsableWindowContext(fallbackContext, options) &&
      typeof retryGetActiveWindow === 'function') {
    retryContext = enrichWindowContext(await retryGetActiveWindow(fallbackContext))
  }

  if (!isUsableWindowContext(retryContext || fallbackContext, options) &&
      typeof probeWindowAtCursor === 'function') {
    cursorContext = enrichWindowContext(await probeWindowAtCursor(retryContext || fallbackContext))
  }

  const targetContext = chooseWindowContext({
    preferredContext: preferred,
    fallbackContext: cursorContext || retryContext || fallbackContext,
    lastContext: reusableLastContext,
    selfProcessNames
  })

  rememberContext(targetContext)
  return targetContext
}

module.exports = {
  resolveWindowContext
}
