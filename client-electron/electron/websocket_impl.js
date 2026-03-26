'use strict'

function resolveWebSocketImpl (options = {}) {
  const globalWebSocket = Object.prototype.hasOwnProperty.call(options, 'globalWebSocket')
    ? options.globalWebSocket
    : globalThis.WebSocket
  const requireFn = options.requireFn || require

  if (typeof globalWebSocket === 'function') {
    return globalWebSocket
  }

  try {
    const wsModule = requireFn('ws')
    if (typeof wsModule === 'function') {
      return wsModule
    }
    if (wsModule && typeof wsModule.WebSocket === 'function') {
      return wsModule.WebSocket
    }
  } catch (err) {
    throw new Error(`No WebSocket implementation available in the Electron main process. Install the ws package. (${err.message})`)
  }

  throw new Error('No WebSocket implementation available in the Electron main process. Install the ws package.')
}

module.exports = {
  resolveWebSocketImpl
}
