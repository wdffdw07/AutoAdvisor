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

test('plan.ready renders the full planned steps and updates active progress', () => {
  const harness = createHarness()

  harness.emit('ipc:ws-message', {
    event: 'plan.ready',
    session_id: 's-1',
    summary: '给素材做弹跳入场',
    total_steps: 4,
    steps: [
      { step_id: 's-1', action: 'click', description: '打开特效面板', reason: '先进入特效区' },
      { step_id: 's-2', action: 'input_text', description: '搜索弹跳入场', reason: '缩小候选范围' },
      { step_id: 's-3', action: 'drag', description: '拖到视频轨道', reason: '把效果应用到素材' },
      { step_id: 's-4', action: 'complete', description: '确认效果预览', reason: '收尾检查' }
    ]
  })

  harness.emit('ipc:ws-message', {
    event: 'plan.step',
    session_id: 's-1',
    step_id: 's-2',
    total_steps: 4,
    action: 'input_text',
    description: '搜索弹跳入场',
    reason: '缩小候选范围'
  })

  const planList = harness.elements.get('planList')
  const progressLabel = harness.elements.get('progressLabel')

  assert.equal(planList.children.length, 4)
  assert.equal(planList.classList.contains('hidden'), false)
  assert.equal(planList.children[0].classList.contains('done'), true)
  assert.equal(planList.children[1].classList.contains('active'), true)
  assert.equal(progressLabel.textContent, '2/4')
})

test('restart hover shows a delayed tooltip, complete sends session.complete, and restart restores the draft state', async () => {
  const harness = createHarness()
  const goalInput = harness.elements.get('goalInput')
  const btnStart = harness.elements.get('btnStart')
  const btnComplete = harness.elements.get('btnComplete')
  const goalRestartButton = harness.elements.get('goalRestartButton')
  const restartTooltip = harness.elements.get('restartTooltip')
  const goalSection = harness.elements.get('goalSection')
  const goalDisplay = harness.elements.get('goalDisplay')

  goalInput.value = '加个弹跳入场的效果'
  btnStart.click()
  await harness.flushAsync()
  harness.sentMessages.length = 0

  goalRestartButton.dispatchEvent({ type: 'mouseenter', clientX: 120, clientY: 48 })
  goalRestartButton.dispatchEvent({ type: 'mousemove', clientX: 128, clientY: 54 })
  harness.advanceTimers(500)

  assert.equal(restartTooltip.classList.contains('hidden'), false)
  assert.match(restartTooltip.textContent, /重新开始/)

  btnComplete.click()

  assert.equal(harness.sentMessages[0].channel, 'session:complete')

  goalRestartButton.click()

  assert.equal(goalSection.classList.contains('hidden'), false)
  assert.equal(goalDisplay.classList.contains('hidden'), true)
  assert.equal(goalInput.value, '加个弹跳入场的效果')
  assert.equal(btnStart.classList.contains('hidden'), false)
  assert.equal(btnComplete.classList.contains('hidden'), true)
})

test('start can proceed without F9 so the main process can resolve the target window in the background', async () => {
  const harness = createHarness()
  const goalInput = harness.elements.get('goalInput')
  const btnStart = harness.elements.get('btnStart')
  const btnComplete = harness.elements.get('btnComplete')
  const goalSection = harness.elements.get('goalSection')
  const goalDisplay = harness.elements.get('goalDisplay')

  harness.setActiveWindowResponse({
    error: 'No target window detected. Press F9 while the target app is focused.',
    process_name: '',
    window_title: '',
    dpi_scale: 1,
    window_box: [0, 0, 0, 0]
  })

  goalInput.value = '加个弹跳入场的效果'
  btnStart.click()
  await harness.flushAsync()

  assert.equal(harness.sentMessages[0].channel, 'session:start')
  assert.equal(harness.sentMessages[0].payload.goal, '加个弹跳入场的效果')
  assert.equal(harness.sentMessages[0].payload.captured_context, null)
  assert.equal(goalSection.classList.contains('hidden'), true)
  assert.equal(goalDisplay.classList.contains('hidden'), false)
  assert.equal(btnComplete.classList.contains('hidden'), false)
})
