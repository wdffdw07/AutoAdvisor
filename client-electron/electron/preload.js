/**
 * preload.js — Electron contextBridge
 *
 * 仅暴露受控的 IPC 通道，禁止 Renderer 直接访问 Node.js 或 Electron API。
 * 严格遵守架构契约 04_architecture_contracts.md §1。
 *
 * Renderer → Main (invoke / send):
 *   mock:start, user:next
 *   ipc:get-active-window (invoke), ipc:capture-region (invoke), ipc:set-overlay (invoke)
 *
 * Main → Renderer (on):
 *   ipc:ws-message, ipc:shortcut-triggered, ipc:ws-status, overlay:show, overlay:hide
 */

'use strict'

const { contextBridge, ipcRenderer } = require('electron')

// 允许的 send 通道（Renderer → Main，单向，无返回值）
const ALLOWED_SEND = new Set([
  'mock:start',
  'user:next'
])

// 允许的 invoke 通道（Renderer → Main，请求-响应，有返回值；协议 §C invoke 通道）
const ALLOWED_INVOKE = new Set([
  'ipc:get-active-window',
  'ipc:capture-region',
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
   * 向 Main 单向发送消息（无返回值）
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
   * 向 Main 发送请求并等待返回值（invoke，协议 §C invoke 通道）
   * @param {string} channel
   * @param {*} data
   * @returns {Promise<*>}
   */
  invoke (channel, data) {
    if (!ALLOWED_INVOKE.has(channel)) {
      console.warn(`[preload] 禁止 invoke 通道: ${channel}`)
      return Promise.resolve(null)
    }
    return ipcRenderer.invoke(channel, data)
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
