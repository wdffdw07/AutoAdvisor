const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

test('capsule markup contains restart icon, done button, and scrollable content region', () => {
  const html = fs.readFileSync(path.join(__dirname, 'capsule.html'), 'utf8')

  assert.match(html, /id="btnComplete"/)
  assert.match(html, /id="goalRestartButton"/)
  assert.match(html, /id="restartTooltip"/)
  assert.match(html, /id="capsuleScrollRegion"/)
})

test('capsule styles make the main content scrollable', () => {
  const css = fs.readFileSync(path.join(__dirname, 'styles.css'), 'utf8')

  assert.match(css, /\.capsule-scroll[\s\S]*overflow-y:\s*auto/)
})
