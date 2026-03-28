'use strict'

const { enrichWindowContext, isUsableWindowContext } = require('./window_context')

class SurfaceTracker {
  constructor ({ selfProcessNames } = {}) {
    this.selfProcessNames = selfProcessNames
    this._surfaceStack = []
    this._activeSurface = null
  }

  update (foregroundSurface) {
    const surface = enrichWindowContext(foregroundSurface)
    if (!isUsableWindowContext(surface, { selfProcessNames: this.selfProcessNames })) {
      return this.snapshot()
    }

    const existingIndex = this._surfaceStack.findIndex((item) => item.hwnd && item.hwnd === surface.hwnd)
    if (existingIndex >= 0) {
      this._surfaceStack = this._surfaceStack.slice(0, existingIndex + 1)
      this._surfaceStack[existingIndex] = surface
      this._activeSurface = surface
      return this.snapshot()
    }

    const ownerIndex = surface.owner_hwnd
      ? this._surfaceStack.findIndex((item) => item.hwnd === surface.owner_hwnd)
      : -1

    if (ownerIndex >= 0) {
      this._surfaceStack = this._surfaceStack.slice(0, ownerIndex + 1)
      this._surfaceStack.push(surface)
      this._activeSurface = surface
      return this.snapshot()
    }

    if (surface.kind === 'main' || !surface.owner_hwnd) {
      this._surfaceStack = [surface]
      this._activeSurface = surface
      return this.snapshot()
    }

    this._surfaceStack = [...this._surfaceStack, surface]
    this._activeSurface = surface
    return this.snapshot()
  }

  snapshot () {
    return {
      active_surface: this._activeSurface ? { ...this._activeSurface } : null,
      surface_stack: this._surfaceStack.map((item) => ({ ...item }))
    }
  }
}

module.exports = {
  SurfaceTracker
}
