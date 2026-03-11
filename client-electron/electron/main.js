/**
 * main.js — Electron 主进程（Step2 Mock）
 *
 * 职责（04_architecture_contracts.md §1 Main 层）：
 *   - 创建胶囊窗口（capsule）与透明叠加层窗口（overlay）
 *   - 注册全局快捷键 F9
 *   - 托管 Mock 会话编排（MockSession）
 *   - 在两个窗口间路由 IPC 消息
 *
 * 不涉及云端 WS 连接（Step3 起引入）。
 */

'use strict'

const { app, BrowserWindow, ipcMain, globalShortcut, screen } = require('electron')
const path = require('path')
const { MockSession } = require('./mock')
const { getActiveWindow, captureRegion } = require('./sniffer')

// ── 窗口引用 ──────────────────────────────────────────────────────────────────
let capsuleWin = null
let overlayWin = null

// ── 当前 Mock 会话 ────────────────────────────────────────────────────────────
let currentSession = null

// ─────────────────────────────────────────────────────────────────────────────
// 窗口工厂
// ─────────────────────────────────────────────────────────────────────────────

function createCapsuleWindow () {
  capsuleWin = new BrowserWindow({
    width:       340,
    height:      520,
    x:           20,
    y:           120,
    frame:       false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable:   false,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          false
    }
  })

  capsuleWin.loadFile(path.join(__dirname, '../renderer/capsule.html'))

  capsuleWin.on('closed', () => { capsuleWin = null })
}

function createOverlayWindow () {
  const { width, height } = screen.getPrimaryDisplay().bounds

  overlayWin = new BrowserWindow({
    width,
    height,
    x:           0,
    y:           0,
    frame:       false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable:   false,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          false
    }
  })

  // 鼠标事件穿透——点击直接穿到下层应用（04_architecture_contracts.md §1）
  overlayWin.setIgnoreMouseEvents(true, { forward: true })
  overlayWin.loadFile(path.join(__dirname, '../renderer/overlay.html'))

  overlayWin.on('closed', () => { overlayWin = null })
}

// ─────────────────────────────────────────────────────────────────────────────
// IPC 路由
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 将 ws:message 推送给胶囊窗口 Renderer
 * 通道名 "ipc:ws-message" 符合协议 §C Main->Renderer
 */
function sendToCapsule (msg) {
  if (capsuleWin && !capsuleWin.isDestroyed()) {
    capsuleWin.webContents.send('ipc:ws-message', msg)
  }
}

/**
 * 将叠加层指令推送给叠加层窗口 Renderer
 * 指令格式: { visible, abs_box?, tooltip? }
 */
function sendToOverlay (cmd) {
  if (overlayWin && !overlayWin.isDestroyed()) {
    const channel = cmd.visible ? 'overlay:show' : 'overlay:hide'
    overlayWin.webContents.send(channel, cmd)
  }
}

// ── mock:start ────────────────────────────────────────────────────────────────
// 胶囊 Renderer 点击"开始"时触发
ipcMain.on('mock:start', (_event, { goal, session_id }) => {
  console.log(`[main] mock:start goal="${goal}" session="${session_id}"`)

  // 通知胶囊 WS 已"连接"（Mock 模拟）
  if (capsuleWin && !capsuleWin.isDestroyed()) {
    capsuleWin.webContents.send('ipc:ws-status', { status: 'connected' })
  }

  currentSession = new MockSession({
    goal,
    sessionId: session_id,
    onMessage: (msg) => {
      console.log(`[main] → capsule: ${msg.event}`, msg.step_id || '')
      sendToCapsule(msg)
    },
    onOverlay: (cmd) => {
      console.log(`[main] → overlay: visible=${cmd.visible}`, cmd.abs_box || '')
      sendToOverlay(cmd)
    }
  })

  currentSession.start()
})

// ── user:next ─────────────────────────────────────────────────────────────────
// 胶囊 Renderer 点击"下一步"时触发
ipcMain.on('user:next', (_event, data) => {
  console.log('[main] user:next', data?.trace_id || '')
  if (currentSession) {
    currentSession.next()
  }
})

// ── ipc:get-active-window ───────────────────────────────────────────────────
// Renderer invoke → Main 查询前台窗口元数据（协议 §C Renderer->Main invoke）
// 返回：{ process_name, window_title, window_box, dpi_scale }
ipcMain.handle('ipc:get-active-window', async () => {
  try {
    const info = await getActiveWindow()
    console.log(`[main] ipc:get-active-window → ${info.process_name} ${JSON.stringify(info.window_box)}`)
    return info
  } catch (err) {
    console.error('[main] ipc:get-active-window error:', err.message)
    return { error: err.message, process_name: '', window_title: '', window_box: [0, 0, 0, 0], dpi_scale: 1 }
  }
})

// ── ipc:capture-region ──────────────────────────────────────────────────────
// Renderer invoke → Main 对指定矩形区域截图（协议 §C Renderer->Main invoke）
// 请求：{ window_box: [x, y, w, h] }
// 返回：{ image_base64: '...' }  或  { error: '...' }
ipcMain.handle('ipc:capture-region', async (_event, { window_box }) => {
  if (!Array.isArray(window_box) || window_box.length < 4) {
    return { error: 'ipc:capture-region: window_box 格式错误' }
  }
  try {
    const image_base64 = await captureRegion(window_box)
    console.log(`[main] ipc:capture-region → base64 length=${image_base64.length}`)
    return { image_base64 }
  } catch (err) {
    console.error('[main] ipc:capture-region error:', err.message)
    return { error: err.message }
  }
})

// ── ipc:set-overlay ─────────────────────────────────────────────────────────
// Renderer invoke → Main 计算坐标并更新叠加层窗口（协议 §C Renderer->Main invoke）
// 请求：{ relative_box, window_box, dpi_scale, tooltip, click_through? }
// 返回：{ success: true }
ipcMain.handle('ipc:set-overlay', (_event, cmd) => {
  try {
    const { relative_box, window_box, tooltip } = cmd || {}
    let abs_box = null
    if (Array.isArray(relative_box) && Array.isArray(window_box)) {
      const [xw, yw] = window_box
      const [xr, yr, wr, hr] = relative_box
      abs_box = [xw + xr, yw + yr, wr, hr]
    }
    sendToOverlay({ visible: true, abs_box, tooltip })
    console.log(`[main] ipc:set-overlay abs_box=${JSON.stringify(abs_box)}`)
    return { success: true }
  } catch (err) {
    console.error('[main] ipc:set-overlay error:', err.message)
    return { success: false, error: err.message }
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// App 生命周期
// ─────────────────────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  createCapsuleWindow()
  createOverlayWindow()

  // 全局快捷键 F9（协议 §C ipc:shortcut-triggered）
  const ok = globalShortcut.register('F9', () => {
    console.log('[main] F9 triggered')
    if (capsuleWin && !capsuleWin.isDestroyed()) {
      capsuleWin.webContents.send('ipc:shortcut-triggered', { accelerator: 'F9' })
    }
  })
  if (!ok) {
    console.warn('[main] F9 快捷键注册失败（可能被其他程序占用）')
  }

  app.on('activate', () => {
    if (!capsuleWin) createCapsuleWindow()
  })
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})

// macOS 关闭所有窗口时不退出（Windows 不需要此逻辑，保留兼容）
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
