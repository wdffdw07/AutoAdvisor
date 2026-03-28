'use strict'

const { contextBridge, ipcRenderer } = require('electron')

const ALLOWED_SEND = new Set([
  'session:start',
  'session:next',
  'session:recover',
  'session:complete'
])

const ALLOWED_INVOKE = new Set([
  'ipc:get-active-window',
  'ipc:capture-region',
  'ipc:set-overlay'
])

const ALLOWED_ON = new Set([
  'ipc:ws-message',
  'ipc:shortcut-triggered',
  'ipc:ws-status',
  'overlay:show',
  'overlay:hide'
])

contextBridge.exposeInMainWorld('electronAPI', {
  send (channel, data) {
    if (!ALLOWED_SEND.has(channel)) {
      console.warn(`[preload] blocked send channel: ${channel}`)
      return
    }
    ipcRenderer.send(channel, data)
  },

  invoke (channel, data) {
    if (!ALLOWED_INVOKE.has(channel)) {
      console.warn(`[preload] blocked invoke channel: ${channel}`)
      return Promise.resolve(null)
    }
    return ipcRenderer.invoke(channel, data)
  },

  on (channel, callback) {
    if (!ALLOWED_ON.has(channel)) {
      console.warn(`[preload] blocked on channel: ${channel}`)
      return () => {}
    }

    const handler = (_event, data) => callback(data)
    ipcRenderer.on(channel, handler)
    return () => ipcRenderer.removeListener(channel, handler)
  },

  removeAllListeners (channel) {
    ipcRenderer.removeAllListeners(channel)
  }
})

