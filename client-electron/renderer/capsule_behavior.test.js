const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function createElementStub (id = '') {
  const listeners = new Map()
  const classes = new Set(['hidden'])
  const element = {
    id,
    style: {},
    dataset: {},
    children: [],
    textContent: '',
    value: '',
    disabled: false,
    focus () {},
    blur () {},
    appendChild (child) {
      this.children.push(child)
      return child
    },
    replaceChildren (...nodes) {
      this.children = [...nodes]
    },
    addEventListener (type, handler) {
      const handlers = listeners.get(type) || []
      handlers.push(handler)
      listeners.set(type, handlers)
    },
    dispatchEvent (event) {
      const handlers = listeners.get(event.type) || []
      for (const handler of handlers) {
        handler({
          ...event,
          currentTarget: this,
          target: this,
          preventDefault () {}
        })
      }
    },
    click () {
      this.dispatchEvent({ type: 'click' })
    },
    setAttribute (name, value) {
      this[name] = value
    },
    getAttribute (name) {
      return this[name]
    },
    classList: {
      add (...tokens) {
        for (const token of tokens) classes.add(token)
      },
      remove (...tokens) {
        for (const token of tokens) classes.delete(token)
      },
      contains (token) {
        return classes.has(token)
      }
    }
  }

  Object.defineProperty(element, 'className', {
    get () {
      return [...classes].join(' ')
    },
    set (value) {
      classes.clear()
      for (const token of String(value).split(/\s+/).filter(Boolean)) {
        classes.add(token)
      }
    }
  })

  Object.defineProperty(element, 'innerHTML', {
    get () {
      return ''
    },
    set () {
      this.children = []
    }
  })

  return element
}

function createHarness () {
  const elements = new Map()
  const eventHandlers = new Map()
  const sentMessages = []
  let timerId = 0
  const timers = new Map()
  let activeWindowResponse = {
    process_name: 'JianyingPro.exe',
    window_title: 'CapCut',
    dpi_scale: 1,
    window_box: [10, 20, 1280, 720]
  }

  const knownIds = [
    'statusBadge',
    'goalSection',
    'goalInput',
    'goalDisplay',
    'goalDisplayText',
    'windowCtxBadge',
    'idleCaptureHint',
    'progressSection',
    'progressFill',
    'progressLabel',
    'planList',
    'stepCard',
    'stepActionBadge',
    'stepDescription',
    'stepTooltip',
    'stepReason',
    'waitingIndicator',
    'waitingText',
    'doneCard',
    'doneSummary',
    'btnStart',
    'btnNext',
    'btnComplete',
    'goalRestartButton',
    'restartTooltip',
    'capsuleScrollRegion'
  ]

  for (const id of knownIds) {
    elements.set(id, createElementStub(id))
  }

  elements.get('goalInput').classList.remove('hidden')
  elements.get('btnStart').classList.remove('hidden')

  const sandbox = {
    console: {
      log () {},
      warn () {},
      error () {}
    },
    document: {
      getElementById (id) {
        if (!elements.has(id)) {
          elements.set(id, createElementStub(id))
        }
        return elements.get(id)
      },
      createElement (tagName) {
        return createElementStub(tagName)
      }
    },
    window: {
      captureFeedback: {},
      electronAPI: {
        on (eventName, handler) {
          eventHandlers.set(eventName, handler)
        },
        send (channel, payload) {
          sentMessages.push({ channel, payload })
        },
        invoke (channel) {
          if (channel === 'ipc:get-active-window') {
            return Promise.resolve(activeWindowResponse)
          }
          return Promise.resolve(null)
        },
        removeAllListeners () {}
      }
    },
    Math,
    setTimeout (fn, delay) {
      timerId += 1
      timers.set(timerId, { fn, delay })
      return timerId
    },
    clearTimeout (id) {
      timers.delete(id)
    }
  }

  sandbox.global = sandbox
  sandbox.globalThis = sandbox

  const scriptPath = path.join(__dirname, 'capsule.js')
  const scriptCode = fs.readFileSync(scriptPath, 'utf8')
  vm.runInNewContext(scriptCode, sandbox, { filename: scriptPath })

  return {
    elements,
    sentMessages,
    emit (eventName, payload) {
      const handler = eventHandlers.get(eventName)
      assert.ok(handler, `expected handler for ${eventName}`)
      handler(payload)
    },
    advanceTimers (maxDelay = Infinity) {
      const readyTimers = [...timers.entries()]
        .filter(([, timer]) => timer.delay <= maxDelay)
        .sort((a, b) => a[0] - b[0])

      for (const [id, timer] of readyTimers) {
        timers.delete(id)
        timer.fn()
      }
    },
    async flushAsync () {
      await new Promise(resolve => setTimeout(resolve, 0))
      await Promise.resolve()
    },
    setActiveWindowResponse (value) {
      activeWindowResponse = value
    }
  }
}

test('start enters planning before the first plan arrives and does not require F9', async () => {
  const harness = createHarness()
  const goalInput = harness.elements.get('goalInput')
  const btnStart = harness.elements.get('btnStart')
  const statusBadge = harness.elements.get('statusBadge')
  const btnNext = harness.elements.get('btnNext')
  const btnComplete = harness.elements.get('btnComplete')

  harness.setActiveWindowResponse({
    error: 'No target window detected.',
    process_name: '',
    window_title: '',
    dpi_scale: 1,
    window_box: [0, 0, 0, 0]
  })

  goalInput.value = 'Add a bounce intro effect'
  btnStart.click()
  await harness.flushAsync()

  assert.equal(harness.sentMessages[0].channel, 'session:start')
  assert.equal(harness.sentMessages[0].payload.captured_context, null)
  assert.match(statusBadge.className, /planning/)
  assert.equal(btnNext.classList.contains('hidden'), true)
  assert.equal(btnComplete.classList.contains('hidden'), true)
})

test('plan.ready replaces the full plan list when a replan arrives', () => {
  const harness = createHarness()

  harness.emit('ipc:ws-message', {
    event: 'plan.ready',
    session_id: 's-1',
    summary: 'Initial plan',
    current_step_index: 1,
    total_steps: 3,
    steps: [
      { step_id: 's-1', action: 'click', description: 'Open Effects', reason: 'Enter the panel' },
      { step_id: 's-2', action: 'input_text', description: 'Search bounce', reason: 'Filter candidates' },
      { step_id: 's-3', action: 'drag', description: 'Drag to timeline', reason: 'Apply the effect' }
    ]
  })

  harness.emit('ipc:ws-message', {
    event: 'plan.ready',
    session_id: 's-1',
    summary: 'Replacement plan',
    current_step_index: 1,
    total_steps: 2,
    steps: [
      { step_id: 's-1b', action: 'click', description: 'Open Export', reason: 'Switch route' },
      { step_id: 's-2b', action: 'click', description: 'Confirm export', reason: 'Finish' }
    ]
  })

  assert.equal(harness.elements.get('planList').children.length, 2)
  assert.equal(harness.elements.get('progressLabel').textContent, '1/2')
  assert.match(harness.elements.get('statusBadge').className, /running/)
})

test('checkpoint wait and recovering states use explicit gating actions', () => {
  const harness = createHarness()
  const statusBadge = harness.elements.get('statusBadge')
  const btnNext = harness.elements.get('btnNext')

  harness.emit('ipc:ws-message', {
    event: 'plan.ready',
    session_id: 's-1',
    summary: 'Plan',
    current_step_index: 1,
    total_steps: 1,
    steps: [
      { step_id: 's-1', action: 'click', description: 'Open Export', reason: 'Start here' }
    ]
  })
  harness.emit('ipc:ws-message', {
    event: 'plan.step',
    session_id: 's-1',
    step_id: 's-1',
    total_steps: 1,
    action: 'click',
    description: 'Open Export',
    reason: 'Start here'
  })
  harness.emit('ipc:ws-message', {
    event: 'guide.highlight',
    session_id: 's-1',
    step_id: 's-1',
    tooltip: 'Click here',
    require_manual_next: true,
    target: { relative_box: [10, 20, 30, 40], confidence: 0.8 }
  })

  assert.match(statusBadge.className, /checkpoint_wait/)
  assert.equal(btnNext.disabled, false)
  assert.equal(btnNext.classList.contains('hidden'), false)

  harness.emit('ipc:ws-message', {
    event: 'session.error',
    session_id: 's-1',
    message: 'Need a narrower target',
    recoverable: true
  })

  assert.match(statusBadge.className, /recovering/)
  assert.equal(btnNext.textContent, 'Retry')
  btnNext.click()
  assert.equal(harness.sentMessages.at(-1).channel, 'session:recover')
  assert.equal(harness.sentMessages.at(-1).payload.recovery_action, 'step_retarget')

  harness.emit('ipc:ws-message', {
    event: 'session.error',
    session_id: 's-1',
    message: 'Blocked',
    recoverable: false
  })

  assert.match(statusBadge.className, /blocked/)
  assert.equal(btnNext.classList.contains('hidden'), true)
})

test('done and restart restore the draft state while preserving the goal draft', async () => {
  const harness = createHarness()
  const goalInput = harness.elements.get('goalInput')
  const btnStart = harness.elements.get('btnStart')
  const btnComplete = harness.elements.get('btnComplete')
  const btnRestart = harness.elements.get('goalRestartButton')
  const doneCard = harness.elements.get('doneCard')
  const goalSection = harness.elements.get('goalSection')
  const goalDisplay = harness.elements.get('goalDisplay')

  goalInput.value = 'Add a bounce intro effect'
  btnStart.click()
  await harness.flushAsync()
  harness.emit('ipc:ws-message', {
    event: 'plan.ready',
    session_id: 's-1',
    summary: 'Plan',
    current_step_index: 1,
    total_steps: 1,
    steps: [
      { step_id: 's-1', action: 'click', description: 'Open Effects', reason: 'Start here' }
    ]
  })

  btnComplete.click()
  assert.equal(harness.sentMessages.at(-1).channel, 'session:complete')

  harness.emit('ipc:ws-message', {
    event: 'session.done',
    session_id: 's-1',
    summary: 'Tutorial complete'
  })

  assert.equal(doneCard.classList.contains('hidden'), false)
  btnRestart.click()

  assert.equal(goalSection.classList.contains('hidden'), false)
  assert.equal(goalDisplay.classList.contains('hidden'), true)
  assert.equal(goalInput.value, 'Add a bounce intro effect')
  assert.equal(btnStart.classList.contains('hidden'), false)
})
