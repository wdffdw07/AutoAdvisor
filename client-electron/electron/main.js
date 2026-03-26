'use strict'

const { app, BrowserWindow, ipcMain, globalShortcut, screen } = require('electron')
const path = require('path')
const { MockSession } = require('./mock')
const { SessionBridge } = require('./session_bridge')
const { getActiveWindow, getWindowAtCursor, captureRegion } = require('./sniffer')
const {
  getSelfProcessNames,
  isUsableWindowContext
} = require('./window_context')
const { resolveWindowContext } = require('./window_context_resolver')
const { resolveWebSocketImpl } = require('./websocket_impl')

let capsuleWin = null
let overlayWin = null
let currentMockSession = null
let sessionBridge = null
let lastNonSelfContext = null

const useMock =
  process.argv.includes('--mock-session') ||
  process.env.ELECTRON_SESSION_MODE === 'mock'
const selfProcessNames = getSelfProcessNames(process.execPath)
const NO_TARGET_WINDOW_MESSAGE = 'No target window detected. Press F9 while the target app is focused.'

function wait (ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function wireWindowDebugLogs (win, label) {
  if (!win || !win.webContents) {
    return
  }

  win.webContents.on('did-finish-load', () => {
    console.log(`[main] ${label} did-finish-load`)
  })

  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    console.log(`[renderer:${label}] level=${level} ${sourceId}:${line} ${message}`)
  })

  win.webContents.on('render-process-gone', (_event, details) => {
    console.error(`[main] ${label} render-process-gone:`, details)
  })
}

function createCapsuleWindow () {
  capsuleWin = new BrowserWindow({
    width: 340,
    height: 520,
    x: 20,
    y: 120,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  capsuleWin.loadFile(path.join(__dirname, '../renderer/capsule.html'))
  wireWindowDebugLogs(capsuleWin, 'capsule')
  capsuleWin.on('closed', () => { capsuleWin = null })
}

function createOverlayWindow () {
  const { width, height } = screen.getPrimaryDisplay().bounds

  overlayWin = new BrowserWindow({
    width,
    height,
    x: 0,
    y: 0,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  overlayWin.setIgnoreMouseEvents(true, { forward: true })
  overlayWin.loadFile(path.join(__dirname, '../renderer/overlay.html'))
  wireWindowDebugLogs(overlayWin, 'overlay')
  overlayWin.on('closed', () => { overlayWin = null })
}

function sendToCapsule (msg) {
  if (capsuleWin && !capsuleWin.isDestroyed()) {
    capsuleWin.webContents.send('ipc:ws-message', msg)
  }
}

function rememberWindowContext (context) {
  if (isUsableWindowContext(context, { selfProcessNames })) {
    lastNonSelfContext = context
  }
}

async function withControlWindowsHidden (probe) {
  const windows = [capsuleWin, overlayWin].filter((win) => win && !win.isDestroyed())
  const states = windows.map((win) => ({
    win,
    wasVisible: win.isVisible(),
    wasFocused: win.isFocused()
  }))

  try {
    for (const state of states) {
      if (state.wasVisible) {
        state.win.hide()
      }
    }

    if (states.some((state) => state.wasVisible)) {
      await wait(120)
    }

    return await probe()
  } finally {
    for (const state of states) {
      if (state.wasVisible && !state.win.isDestroyed()) {
        state.win.show()
        if (state.wasFocused) {
          state.win.focus()
        }
      }
    }
  }
}

async function resolveTargetWindowContext (preferredContext) {
  return resolveWindowContext({
    preferredContext,
    getActiveWindow,
    retryGetActiveWindow: async () => {
      const retriedContext = await withControlWindowsHidden(async () => getActiveWindow())
      console.log(`[main] background retry captured -> ${retriedContext.process_name} ${JSON.stringify(retriedContext.window_box)}`)
      return retriedContext
    },
    probeWindowAtCursor: async () => {
      const cursorContext = await withControlWindowsHidden(async () => getWindowAtCursor())
      console.log(`[main] cursor probe captured -> ${cursorContext.process_name} ${JSON.stringify(cursorContext.window_box)}`)
      return cursorContext
    },
    lastContext: lastNonSelfContext,
    selfProcessNames,
    rememberContext: rememberWindowContext
  })
}

function buildAbsBox (relativeBox, windowBox) {
  if (!Array.isArray(relativeBox) || !Array.isArray(windowBox)) {
    return null
  }

  const [xw, yw] = windowBox
  const [xr, yr, wr, hr] = relativeBox
  return [xw + xr, yw + yr, wr, hr]
}

function sendToOverlay (cmd) {
  if (!overlayWin || overlayWin.isDestroyed()) {
    return
  }

  if (!cmd || !cmd.visible) {
    overlayWin.webContents.send('overlay:hide', { visible: false, tooltip: cmd && cmd.tooltip ? cmd.tooltip : '' })
    return
  }

  const absBox = cmd.abs_box || buildAbsBox(cmd.relative_box, cmd.window_box)
  overlayWin.webContents.send('overlay:show', {
    visible: true,
    abs_box: absBox,
    tooltip: cmd.tooltip || '',
    confidence: cmd.confidence
  })
}

async function captureSnapshot ({ context } = {}) {
  const targetContext = await resolveTargetWindowContext(context)

  if (!targetContext || !Array.isArray(targetContext.window_box)) {
    throw new Error(NO_TARGET_WINDOW_MESSAGE)
  }

  const image_base64 = await captureRegion(targetContext.window_box)
  return {
    context: targetContext,
    image_base64
  }
}

function publishWsStatus (status) {
  if (capsuleWin && !capsuleWin.isDestroyed()) {
    capsuleWin.webContents.send('ipc:ws-status', { status })
  }
}

function ensureSessionBridge () {
  if (sessionBridge) {
    return sessionBridge
  }

  sessionBridge = new SessionBridge({
    serverUrl: process.env.COPILOT_WS_URL || 'ws://127.0.0.1:8000/ws',
    sendToCapsule,
    sendToOverlay,
    captureSnapshot,
    WebSocketImpl: resolveWebSocketImpl(),
    onStatus: publishWsStatus
  })

  return sessionBridge
}

function startMockSession ({ goal, sessionId }) {
  publishWsStatus('connected')

  currentMockSession = new MockSession({
    goal,
    sessionId,
    onMessage: (msg) => {
      console.log(`[main] -> capsule: ${msg.event}`, msg.step_id || '')
      sendToCapsule(msg)
    },
    onOverlay: (cmd) => {
      console.log(`[main] -> overlay: visible=${cmd.visible}`, cmd.abs_box || '')
      sendToOverlay(cmd)
    }
  })

  currentMockSession.start()
}

ipcMain.on('session:start', async (_event, payload) => {
  const goal = payload && payload.goal ? payload.goal : ''
  const capturedContext = payload && payload.captured_context ? payload.captured_context : null

  console.log(`[main] session:start mode=${useMock ? 'mock' : 'remote'} goal="${goal}"`)

  if (useMock) {
    startMockSession({
      goal,
      sessionId: payload && payload.session_id ? payload.session_id : `s-mock-${Date.now()}`
    })
    return
  }

  try {
    const bridge = ensureSessionBridge()
    await bridge.startSession({ goal, context: capturedContext })
  } catch (err) {
    console.error('[main] session:start error:', err.message)
    publishWsStatus('disconnected')
    sendToCapsule({
      protocol_version: 'v1',
      event: 'session.error',
      code: 'E_INTERNAL',
      message: err.message,
      recoverable: true
    })
  }
})

ipcMain.on('session:next', async () => {
  console.log(`[main] session:next mode=${useMock ? 'mock' : 'remote'}`)

  if (useMock) {
    if (currentMockSession) {
      currentMockSession.next()
    }
    return
  }

  try {
    const bridge = ensureSessionBridge()
    await bridge.continueSession()
  } catch (err) {
    console.error('[main] session:next error:', err.message)
    sendToCapsule({
      protocol_version: 'v1',
      event: 'session.error',
      code: 'E_INTERNAL',
      message: err.message,
      recoverable: true
    })
  }
})

ipcMain.on('session:complete', async () => {
  console.log(`[main] session:complete mode=${useMock ? 'mock' : 'remote'}`)

  if (useMock) {
    if (currentMockSession && typeof currentMockSession.complete === 'function') {
      currentMockSession.complete()
    }
    return
  }

  try {
    const bridge = ensureSessionBridge()
    await bridge.completeSession()
  } catch (err) {
    console.error('[main] session:complete error:', err.message)
    sendToCapsule({
      protocol_version: 'v1',
      event: 'session.error',
      code: 'E_INTERNAL',
      message: err.message,
      recoverable: true
    })
  }
})

ipcMain.handle('ipc:get-active-window', async () => {
  try {
    const info = await resolveTargetWindowContext()
    if (!info) {
      console.warn('[main] ipc:get-active-window -> no target window available')
      return { error: NO_TARGET_WINDOW_MESSAGE, process_name: '', window_title: '', window_box: [0, 0, 0, 0], dpi_scale: 1 }
    }
    console.log(`[main] ipc:get-active-window -> ${info.process_name} ${JSON.stringify(info.window_box)}`)
    return info
  } catch (err) {
    console.error('[main] ipc:get-active-window error:', err.message)
    return { error: err.message, process_name: '', window_title: '', window_box: [0, 0, 0, 0], dpi_scale: 1 }
  }
})

ipcMain.handle('ipc:capture-region', async (_event, { window_box }) => {
  if (!Array.isArray(window_box) || window_box.length < 4) {
    return { error: 'ipc:capture-region: window_box format invalid' }
  }
  try {
    const image_base64 = await captureRegion(window_box)
    console.log(`[main] ipc:capture-region -> base64 length=${image_base64.length}`)
    return { image_base64 }
  } catch (err) {
    console.error('[main] ipc:capture-region error:', err.message)
    return { error: err.message }
  }
})

ipcMain.handle('ipc:set-overlay', (_event, cmd) => {
  try {
    sendToOverlay(cmd)
    return { success: true }
  } catch (err) {
    console.error('[main] ipc:set-overlay error:', err.message)
    return { success: false, error: err.message }
  }
})

async function handleShortcutTriggered () {
  console.log('[main] F9 triggered')

  let payload = { accelerator: 'F9' }

  try {
    const context = await resolveTargetWindowContext()
    if (context) {
      payload = { accelerator: 'F9', captured_context: context }
      console.log(`[main] F9 captured target -> ${context.process_name} ${JSON.stringify(context.window_box)}`)
    } else {
      payload = { accelerator: 'F9', error: NO_TARGET_WINDOW_MESSAGE }
      console.warn('[main] F9 target window unavailable')
    }
  } catch (err) {
    payload = { accelerator: 'F9', error: err.message }
    console.error('[main] F9 capture error:', err.message)
  }

  if (capsuleWin && !capsuleWin.isDestroyed()) {
    if (capsuleWin.isMinimized()) {
      capsuleWin.restore()
    }
    capsuleWin.show()
    capsuleWin.focus()
    capsuleWin.webContents.send('ipc:shortcut-triggered', payload)
  }
}

app.whenReady().then(() => {
  createCapsuleWindow()
  createOverlayWindow()

  console.log(`[main] session mode: ${useMock ? 'mock' : 'remote'}`)

  const ok = globalShortcut.register('F9', () => {
    void handleShortcutTriggered()
  })

  if (!ok) {
    console.warn('[main] F9 registration failed')
  }

  app.on('activate', () => {
    if (!capsuleWin) createCapsuleWindow()
  })
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
  if (sessionBridge) {
    sessionBridge.close()
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
