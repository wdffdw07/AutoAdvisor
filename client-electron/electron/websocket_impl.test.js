const test = require('node:test')
const assert = require('node:assert/strict')

const { resolveWebSocketImpl } = require('./websocket_impl')

test('resolveWebSocketImpl prefers the provided global WebSocket', () => {
  class BrowserWebSocket {}

  const impl = resolveWebSocketImpl({
    globalWebSocket: BrowserWebSocket,
    requireFn: () => {
      throw new Error('should not require ws when global WebSocket exists')
    }
  })

  assert.equal(impl, BrowserWebSocket)
})

test('resolveWebSocketImpl falls back to the ws package when global WebSocket is unavailable', () => {
  class NodeWebSocket {}

  const impl = resolveWebSocketImpl({
    globalWebSocket: undefined,
    requireFn: (id) => {
      assert.equal(id, 'ws')
      return { WebSocket: NodeWebSocket }
    }
  })

  assert.equal(impl, NodeWebSocket)
})

test('resolveWebSocketImpl throws a helpful error when no WebSocket implementation is available', () => {
  assert.throws(
    () => resolveWebSocketImpl({
      globalWebSocket: undefined,
      requireFn: () => {
        throw new Error('module not found')
      }
    }),
    /Install the ws package/
  )
})
