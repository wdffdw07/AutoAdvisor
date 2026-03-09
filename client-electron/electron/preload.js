/**
 * preload.js — Electron contextBridge
 *
 * 仅暴露受控的 IPC 通道，禁止 Renderer 直接访问 Node.js 或 Electron API。
 * 严格遵守架构契约 04_architecture_contracts.md §1。
 *
 * Renderer → Main (invoke / send):
 *   mock:start, user:next, ipc:set-overlay
 *
 * Main → Renderer (on):
 *   ipc:ws-message, ipc:shortcut-triggered, ipc:ws-status, overlay:show, overlay:hide
 */

'use strict'

const { contextBridge, ipcRenderer } = require('electron')

// 允许的 send 通道（Renderer → Main，单向）
const ALLOWED_SEND = new Set([
  'mock:start',
  'user:next',
  'ipc:set-overlay'
])

// 允许的 on 通道（Main → Renderer，监听）
const ALLOWED_ON = new Set([
  'ipc:ws-message',
  'ipc:shortcut-triggered',
  'ipc:ws-status',
  'overlay:show',
  'overlay:hide'
])

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * 向 Main 单向发送消息
   * @param {string} channel
   * @param {*} data
   */
  send (channel, data) {
    if (!ALLOWED_SEND.has(channel)) {
      console.warn(`[preload] 禁止发送通道: ${channel}`)
      return
    }
    ipcRenderer.send(channel, data)
  },

  /**
   * 监听 Main 下发的消息
   * @param {string} channel
   * @param {function} callback  (data) => void
   * @returns {function} unsubscribe
   */
  on (channel, callback) {
    if (!ALLOWED_ON.has(channel)) {
      console.warn(`[preload] 禁止监听通道: ${channel}`)
      return () => {}
    }
    const handler = (_event, data) => callback(data)
    ipcRenderer.on(channel, handler)
    return () => ipcRenderer.removeListener(channel, handler)
  },

  /**
   * 移除某通道全部监听器（清理用）
   * @param {string} channel
   */
  removeAllListeners (channel) {
    ipcRenderer.removeAllListeners(channel)
  }
})
