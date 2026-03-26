const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function createElementStub () {
  return {
    classList: {
      add () {},
      remove () {}
    },
    style: {},
    textContent: '',
    className: '',
    value: '',
    disabled: false,
    focus () {},
    addEventListener () {}
  }
}

test('capture_feedback and capsule scripts can bootstrap in the same browser context', () => {
  const sandbox = {
    console: {
      log () {},
      warn () {},
      error () {}
    },
    document: {
      getElementById () {
        return createElementStub()
      }
    },
    window: {
      electronAPI: {
        on () {},
        send () {},
        invoke () {
          return Promise.resolve(null)
        },
        removeAllListeners () {}
      }
    },
    Math,
    setTimeout,
    clearTimeout
  }

  sandbox.global = sandbox
  sandbox.globalThis = sandbox

  const captureFeedbackPath = path.join(__dirname, 'capture_feedback.js')
  const capsulePath = path.join(__dirname, 'capsule.js')

  const captureFeedbackCode = fs.readFileSync(captureFeedbackPath, 'utf8')
  const capsuleCode = fs.readFileSync(capsulePath, 'utf8')

  vm.runInNewContext(captureFeedbackCode, sandbox, { filename: captureFeedbackPath })

  assert.doesNotThrow(() => {
    vm.runInNewContext(capsuleCode, sandbox, { filename: capsulePath })
  })
})
