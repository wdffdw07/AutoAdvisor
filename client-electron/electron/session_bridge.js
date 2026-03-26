'use strict'

const { randomUUID } = require('node:crypto')

function buildSessionStartMessage ({ sessionId, traceId, goal, context, image_base64 }) {
  return {
    protocol_version: 'v1',
    trace_id: traceId,
    session_id: sessionId,
    event: 'session.start',
    goal,
    context,
    image_base64
  }
}

function buildContextUpdateMessage ({ sessionId, traceId, context, image_base64 }) {
  return {
    protocol_version: 'v1',
    trace_id: traceId,
    session_id: sessionId,
    event: 'context.update',
    context,
    image_base64
  }
}

function buildUserNextMessage ({ sessionId, traceId }) {
  return {
    protocol_version: 'v1',
    trace_id: traceId,
    session_id: sessionId,
    event: 'user.next'
  }
}

function buildSessionCompleteMessage ({ sessionId, traceId }) {
  return {
    protocol_version: 'v1',
    trace_id: traceId,
    session_id: sessionId,
    event: 'session.complete'
  }
}

function toOverlayCommand (serverEvent) {
  if (serverEvent && serverEvent.event === 'guide.highlight') {
    return {
      visible: true,
      relative_box: serverEvent.target && serverEvent.target.relative_box,
      tooltip: serverEvent.tooltip || '',
      confidence: serverEvent.target && serverEvent.target.confidence
    }
  }

  return {
    visible: false,
    tooltip: serverEvent && serverEvent.tooltip ? serverEvent.tooltip : ''
  }
}

function isManualContinuation (serverEvent) {
  if (!serverEvent) return false
  if (serverEvent.event === 'guide.wait_manual') return true
  return serverEvent.event === 'guide.highlight' && serverEvent.require_manual_next === true
}

class SessionBridge {
  constructor ({
    serverUrl,
    sendToCapsule,
    sendToOverlay,
    captureSnapshot,
    WebSocketImpl = WebSocket,
    onStatus = () => {}
  }) {
    this.serverUrl = serverUrl
    this.sendToCapsule = sendToCapsule
    this.sendToOverlay = sendToOverlay
    this.captureSnapshot = captureSnapshot
    this.WebSocketImpl = WebSocketImpl
    this.onStatus = onStatus

    this.socket = null
    this.sessionId = null
    this.lastGuideEvent = null
    this.lastContext = null
    this.pendingMessages = []
    this.status = 'disconnected'
  }

  async startSession ({ goal, context } = {}) {
    const snapshot = await this.captureSnapshot({ context })
    this.sessionId = randomUUID()
    this.lastGuideEvent = null
    this.lastContext = snapshot.context

    this._send(
      buildSessionStartMessage({
        sessionId: this.sessionId,
        traceId: randomUUID(),
        goal,
        context: snapshot.context,
        image_base64: snapshot.image_base64
      })
    )
  }

  async continueSession ({ manual } = {}) {
    if (!this.sessionId) {
      return
    }

    const shouldSendUserNext = manual !== undefined ? manual : isManualContinuation(this.lastGuideEvent)

    if (shouldSendUserNext) {
      this._send(
        buildUserNextMessage({
          sessionId: this.sessionId,
          traceId: randomUUID()
        })
      )
    }

    const snapshot = await this.captureSnapshot({ context: this.lastContext })
    this.lastContext = snapshot.context
    this._send(
      buildContextUpdateMessage({
        sessionId: this.sessionId,
        traceId: randomUUID(),
        context: snapshot.context,
        image_base64: snapshot.image_base64
      })
    )
  }

  async completeSession () {
    if (!this.sessionId) {
      return
    }

    this._send(
      buildSessionCompleteMessage({
        sessionId: this.sessionId,
        traceId: randomUUID()
      })
    )
  }

  close () {
    if (this.socket && typeof this.socket.close === 'function') {
      this.socket.close()
    }
    this.socket = null
    this.pendingMessages = []
    this._setStatus('disconnected')
  }

  _setStatus (status) {
    this.status = status
    this.onStatus(status)
  }

  _ensureSocket () {
    const readyState = this.socket && typeof this.socket.readyState === 'number'
      ? this.socket.readyState
      : null

    if (this.socket && (readyState === null || readyState === 0 || readyState === 1)) {
      return
    }

    this._setStatus('reconnecting')
    this.socket = new this.WebSocketImpl(this.serverUrl)

    this.socket.onopen = () => {
      this._setStatus('connected')
      while (this.pendingMessages.length > 0) {
        this.socket.send(this.pendingMessages.shift())
      }
    }

    this.socket.onmessage = (event) => {
      const msg = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
      this.sendToCapsule(msg)

      if (msg.event === 'guide.highlight' || msg.event === 'guide.wait_manual' || msg.event === 'session.done' || msg.event === 'session.error') {
        const overlayCommand = toOverlayCommand(msg)
        if (this.lastContext && overlayCommand.visible) {
          overlayCommand.window_box = this.lastContext.window_box
          overlayCommand.dpi_scale = this.lastContext.dpi_scale
        }
        this.sendToOverlay(overlayCommand)
      }

      if (msg.event === 'guide.highlight' || msg.event === 'guide.wait_manual') {
        this.lastGuideEvent = msg
      }
    }

    this.socket.onclose = () => {
      this._setStatus('disconnected')
    }

    this.socket.onerror = () => {
      if (this.status !== 'disconnected') {
        this._setStatus('disconnected')
      }
    }
  }

  _send (payload) {
    this._ensureSocket()

    const text = JSON.stringify(payload)
    const readyState = this.socket && typeof this.socket.readyState === 'number'
      ? this.socket.readyState
      : null

    if (this.socket && (readyState === null || readyState === 1)) {
      this.socket.send(text)
      return
    }

    this.pendingMessages.push(text)
  }
}

module.exports = {
  SessionBridge,
  buildSessionStartMessage,
  buildContextUpdateMessage,
  buildSessionCompleteMessage,
  buildUserNextMessage,
  toOverlayCommand,
  isManualContinuation
}
