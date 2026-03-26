'use strict'

const path = require('path')

function normalizeProcessName (processName) {
  return String(processName || '').trim().toLowerCase()
}

function getSelfProcessNames (execPath = process.execPath) {
  const names = new Set()
  const basename = normalizeProcessName(path.basename(execPath))

  if (basename) {
    names.add(basename)
  }

  names.add('electron.exe')
  names.add('electron')
  names.add('codex.exe')
  names.add('codex')
  return names
}

function hasWindowBox (context) {
  return Boolean(context) && Array.isArray(context.window_box) && context.window_box.length >= 4
}

function isSelfWindowContext (context, { execPath, selfProcessNames } = {}) {
  if (!hasWindowBox(context)) {
    return false
  }

  const names = selfProcessNames || getSelfProcessNames(execPath)
  return names.has(normalizeProcessName(context.process_name))
}

function isUsableWindowContext (context, options = {}) {
  return hasWindowBox(context) && !isSelfWindowContext(context, options)
}

function chooseWindowContext ({
  preferredContext,
  fallbackContext,
  lastContext,
  execPath,
  selfProcessNames
} = {}) {
  const options = { execPath, selfProcessNames }

  if (isUsableWindowContext(preferredContext, options)) {
    return preferredContext
  }

  if (isUsableWindowContext(fallbackContext, options)) {
    return fallbackContext
  }

  if (isUsableWindowContext(lastContext, options)) {
    return lastContext
  }

  return null
}

module.exports = {
  chooseWindowContext,
  getSelfProcessNames,
  hasWindowBox,
  isSelfWindowContext,
  isUsableWindowContext,
  normalizeProcessName
}
