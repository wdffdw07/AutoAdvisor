'use strict'

const path = require('path')

function normalizeProcessName (processName) {
  return String(processName || '').trim().toLowerCase()
}

function normalizeHandle (value) {
  if (value === undefined || value === null) {
    return ''
  }
  return String(value).trim()
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

function extractTitleKeywords (windowTitle) {
  const parts = String(windowTitle || '').toLowerCase().match(/[a-z0-9\u4e00-\u9fff]+/g) || []
  const seen = new Set()
  const keywords = []

  for (const part of parts) {
    if (part.length < 2 || seen.has(part)) {
      continue
    }
    seen.add(part)
    keywords.push(part)
  }

  return keywords.slice(0, 6)
}

function deriveWindowKind (context) {
  if (!context) {
    return 'unknown'
  }

  if (context.kind) {
    return context.kind
  }

  const processName = normalizeProcessName(context.process_name)
  const title = String(context.window_title || '').toLowerCase()
  const owner = normalizeHandle(context.owner_hwnd)
  const looksLikePicker = /(open|save|browse|select|choose|import|export)/.test(title)

  if (processName === 'explorer.exe' && looksLikePicker) {
    return 'picker'
  }

  if (owner && looksLikePicker) {
    return 'picker'
  }

  if (owner) {
    return 'dialog'
  }

  return 'main'
}

function buildSurfaceSignature (context) {
  const processName = normalizeProcessName(context && context.process_name)
  const kind = deriveWindowKind(context)
  const hwnd = normalizeHandle(context && context.hwnd)
  const keywords = Array.isArray(context && context.title_keywords)
    ? context.title_keywords
    : extractTitleKeywords(context && context.window_title)

  return [processName, kind, hwnd || 'nohwnd', keywords.slice(0, 4).join('+')]
    .filter(Boolean)
    .join('|')
}

function enrichWindowContext (context) {
  if (!context || typeof context !== 'object') {
    return context || null
  }

  context.hwnd = normalizeHandle(context.hwnd)
  context.owner_hwnd = normalizeHandle(context.owner_hwnd)
  context.title_keywords = extractTitleKeywords(context.window_title)
  context.kind = deriveWindowKind(context)
  context.surface_signature = buildSurfaceSignature(context)
  return context
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
  const preferred = enrichWindowContext(preferredContext)
  const fallback = enrichWindowContext(fallbackContext)
  const last = enrichWindowContext(lastContext)

  if (isUsableWindowContext(preferred, options)) {
    return preferred
  }

  if (isUsableWindowContext(fallback, options)) {
    return fallback
  }

  if (isUsableWindowContext(last, options)) {
    return last
  }

  return null
}

module.exports = {
  buildSurfaceSignature,
  chooseWindowContext,
  deriveWindowKind,
  enrichWindowContext,
  extractTitleKeywords,
  getSelfProcessNames,
  hasWindowBox,
  isSelfWindowContext,
  isUsableWindowContext,
  normalizeHandle,
  normalizeProcessName
}
