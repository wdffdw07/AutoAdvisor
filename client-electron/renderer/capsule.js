'use strict'

const captureFeedback = window.captureFeedback || {}
const getShortcutCaptureFeedback = captureFeedback.buildShortcutCaptureFeedback || (() => null)
const getWindowCaptureLabel = captureFeedback.formatWindowCaptureLabel || (() => '')

const elStatus = document.getElementById('statusBadge')
const elGoalSection = document.getElementById('goalSection')
const elGoalInput = document.getElementById('goalInput')
const elGoalDisplay = document.getElementById('goalDisplay')
const elGoalText = document.getElementById('goalDisplayText')
const elWindowCtx = document.getElementById('windowCtxBadge')
const elIdleCaptureHint = document.getElementById('idleCaptureHint')
const elScrollRegion = document.getElementById('capsuleScrollRegion')
const elProgressSec = document.getElementById('progressSection')
const elProgressFill = document.getElementById('progressFill')
const elProgressLbl = document.getElementById('progressLabel')
const elPlanList = document.getElementById('planList')
const elStepCard = document.getElementById('stepCard')
const elActionBadge = document.getElementById('stepActionBadge')
const elDescription = document.getElementById('stepDescription')
const elTooltip = document.getElementById('stepTooltip')
const elReason = document.getElementById('stepReason')
const elWaiting = document.getElementById('waitingIndicator')
const elWaitingText = document.getElementById('waitingText')
const elDoneCard = document.getElementById('doneCard')
const elDoneSummary = document.getElementById('doneSummary')
const elRestartTooltip = document.getElementById('restartTooltip')
const btnStart = document.getElementById('btnStart')
const btnNext = document.getElementById('btnNext')
const btnComplete = document.getElementById('btnComplete')
const btnRestart = document.getElementById('goalRestartButton')

const RETRY_HINT = 'Please focus the target app and press F9 again.'
const RESTART_TOOLTIP_LABEL = 'Restart this tutorial'
const ACTION_MAP = {
  click: { label: 'Click', cls: 'click' },
  drag: { label: 'Drag', cls: 'drag' },
  input_text: { label: 'Type', cls: 'input_text' },
  text: { label: 'Type', cls: 'input_text' },
  scroll: { label: 'Scroll', cls: 'scroll' },
  observe: { label: 'Observe', cls: 'wait' },
  wait: { label: 'Wait', cls: 'wait' },
  complete: { label: 'Done', cls: 'click' }
}

let sessionId = null
let plannedSteps = []
let currentStepIndex = 0
let uiState = 'draft'
let currentWindowCtx = null
let currentCaptureError = ''
let restartTooltipTimer = null
let lastPointerPosition = { x: 0, y: 0 }

function show (el) {
  if (el) el.classList.remove('hidden')
}

function hide (el) {
  if (el) el.classList.add('hidden')
}

function setChildren (el, children) {
  if (!el) return
  if (typeof el.replaceChildren === 'function') {
    el.replaceChildren(...children)
    return
  }
  el.innerHTML = ''
  el.children = children
}

function setStatus (state, label) {
  if (!elStatus) return
  elStatus.className = `status-badge ${state}`
  elStatus.textContent = label
}

function simpleId () {
  return Math.random().toString(36).slice(2)
}

function normalizeStepId (stepId, fallbackIndex) {
  if (stepId) return stepId
  return `s-${String(fallbackIndex).padStart(3, '0')}`
}

function parseStepIndex (stepId) {
  if (!stepId) return 0
  const match = String(stepId).match(/(\d+)$/)
  return match ? parseInt(match[1], 10) : 0
}

function normalizePlanStep (step, index) {
  return {
    step_id: normalizeStepId(step.step_id, index),
    action: step.action || 'click',
    description: step.description || step.tooltip || `Step ${index}`,
    reason: step.reason || '',
    require_manual_next: Boolean(step.require_manual_next)
  }
}

function isValidWindowContext (ctx) {
  return Boolean(
    ctx &&
    !ctx.error &&
    Array.isArray(ctx.window_box) &&
    ctx.window_box.length === 4 &&
    Number(ctx.window_box[2]) > 0 &&
    Number(ctx.window_box[3]) > 0
  )
}

function updateRestartTooltipPosition (x, y) {
  if (!elRestartTooltip) return
  elRestartTooltip.style.left = `${x + 12}px`
  elRestartTooltip.style.top = `${y + 12}px`
}

function hideRestartTooltip () {
  if (restartTooltipTimer) {
    clearTimeout(restartTooltipTimer)
    restartTooltipTimer = null
  }
  hide(elRestartTooltip)
}

function scheduleRestartTooltip () {
  hideRestartTooltip()
  restartTooltipTimer = setTimeout(() => {
    elRestartTooltip.textContent = RESTART_TOOLTIP_LABEL
    updateRestartTooltipPosition(lastPointerPosition.x, lastPointerPosition.y)
    show(elRestartTooltip)
    restartTooltipTimer = null
  }, 400)
}

function renderWindowContextFeedback () {
  const detailText = currentCaptureError || getWindowCaptureLabel(currentWindowCtx) || ''
  if (elWindowCtx) {
    elWindowCtx.textContent = detailText
  }
  if (elIdleCaptureHint) {
    elIdleCaptureHint.textContent = detailText
  }
}

function setDraftStatus () {
  if (currentCaptureError) {
    setStatus('error', 'Need capture')
    return
  }

  if (currentWindowCtx) {
    setStatus('captured', 'Captured')
    return
  }

  setStatus('idle', 'Idle')
}

function updateProgress (step, total) {
  const safeTotal = total > 0 ? total : 0
  const safeStep = safeTotal > 0 ? Math.min(Math.max(step, 0), safeTotal) : 0
  const pct = safeTotal > 0 ? Math.round((safeStep / safeTotal) * 100) : 0

  currentStepIndex = safeStep
  elProgressFill.style.width = `${pct}%`
  elProgressLbl.textContent = `${safeStep}/${safeTotal}`

  if (safeTotal > 0) {
    show(elProgressSec)
  } else {
    hide(elProgressSec)
  }
}

function renderPlanList () {
  if (!plannedSteps.length) {
    setChildren(elPlanList, [])
    hide(elPlanList)
    return
  }

  const items = plannedSteps.map((step, index) => {
    const item = document.createElement('div')
    item.className = 'plan-item'

    const stepNumber = index + 1
    if (currentStepIndex > 0 && stepNumber < currentStepIndex) {
      item.classList.add('done')
    } else if (stepNumber === currentStepIndex) {
      item.classList.add('active')
    }

    const header = document.createElement('div')
    header.className = 'plan-item-header'

    const stepIndex = document.createElement('div')
    stepIndex.className = 'plan-item-index'
    stepIndex.textContent = `STEP ${stepNumber}`

    const stepAction = document.createElement('div')
    stepAction.className = 'plan-item-action'
    stepAction.textContent = (ACTION_MAP[step.action] || { label: step.action }).label

    const description = document.createElement('div')
    description.className = 'plan-item-description'
    description.textContent = step.description

    header.appendChild(stepIndex)
    header.appendChild(stepAction)
    item.appendChild(header)
    item.appendChild(description)

    if (step.reason) {
      const reason = document.createElement('div')
      reason.className = 'plan-item-index'
      reason.textContent = step.reason
      item.appendChild(reason)
    }

    return item
  })

  setChildren(elPlanList, items)
  show(elPlanList)
}

function clearExecutionPanels () {
  hide(elStepCard)
  hide(elWaiting)
  hide(elDoneCard)
  elTooltip.textContent = ''
  elReason.textContent = ''
  elDescription.textContent = ''
}

function ensureInteractiveShell () {
  show(elScrollRegion)
  show(elGoalDisplay)
  show(btnRestart)
}

function switchToDraft ({ preserveGoal = false, preserveContext = true } = {}) {
  const nextGoal = preserveGoal ? (elGoalText.textContent || elGoalInput.value || '') : ''

  uiState = 'draft'
  sessionId = null
  plannedSteps = []
  currentStepIndex = 0

  if (!preserveContext) {
    currentWindowCtx = null
    currentCaptureError = ''
  }

  hideRestartTooltip()
  show(elGoalSection)
  hide(elScrollRegion)
  hide(elGoalDisplay)
  hide(elProgressSec)
  hide(elPlanList)
  clearExecutionPanels()
  show(btnStart)
  hide(btnNext)
  hide(btnComplete)
  hide(btnRestart)
  btnNext.disabled = true
  btnNext.textContent = 'Next'
  btnComplete.disabled = false
  elGoalInput.value = nextGoal
  updateProgress(0, 0)
  renderWindowContextFeedback()
  setDraftStatus()
}

function switchToPlanning (goal, sid) {
  uiState = 'planning'
  sessionId = sid
  plannedSteps = []
  currentStepIndex = 0

  setStatus('planning', 'Planning')
  hide(elGoalSection)
  show(elScrollRegion)
  elGoalText.textContent = goal
  show(elGoalDisplay)
  show(btnRestart)
  renderWindowContextFeedback()
  updateProgress(0, 0)
  renderPlanList()
  clearExecutionPanels()
  hide(btnStart)
  hide(btnNext)
  hide(btnComplete)
}

function enterRunningState () {
  uiState = 'running'
  setStatus('running', 'Guiding')
  ensureInteractiveShell()
  show(btnNext)
  show(btnComplete)
  btnNext.textContent = 'Next'
}

function switchToDone (summary) {
  uiState = 'done'
  setStatus('done', 'Done')
  ensureInteractiveShell()
  hide(elWaiting)
  hide(elStepCard)
  elDoneSummary.textContent = summary || 'Tutorial complete'
  show(elDoneCard)
  hide(btnNext)
  hide(btnComplete)

  if (plannedSteps.length) {
    updateProgress(plannedSteps.length, plannedSteps.length)
    renderPlanList()
  }
}

function upsertPlanStep (step) {
  const normalized = normalizePlanStep(step, plannedSteps.length + 1)
  const numericId = parseStepIndex(normalized.step_id)
  const existingIndex = plannedSteps.findIndex((item) => parseStepIndex(item.step_id) === numericId)

  if (existingIndex >= 0) {
    plannedSteps[existingIndex] = { ...plannedSteps[existingIndex], ...normalized }
    return existingIndex + 1
  }

  plannedSteps.push(normalized)
  return plannedSteps.length
}

function applyCurrentStep (msg) {
  const stepIndex = upsertPlanStep({
    step_id: msg.step_id,
    action: msg.action,
    description: msg.description,
    reason: msg.reason,
    require_manual_next: msg.require_manual_next
  })

  updateProgress(stepIndex, msg.total_steps || plannedSteps.length)
  renderPlanList()

  const actionMeta = ACTION_MAP[msg.action] || { label: msg.action || 'Act', cls: 'click' }
  elActionBadge.textContent = actionMeta.label
  elActionBadge.className = `step-action-badge ${actionMeta.cls}`
  elDescription.textContent = msg.description || ''
  elTooltip.textContent = ''

  if (msg.reason) {
    elReason.textContent = msg.reason
    show(elReason)
  } else {
    hide(elReason)
  }

  hide(elWaiting)
  hide(elDoneCard)
  show(elStepCard)
}

function handlePlanReady (msg) {
  enterRunningState()
  plannedSteps = Array.isArray(msg.steps)
    ? msg.steps.map((step, index) => normalizePlanStep(step, index + 1))
    : []

  updateProgress(Number(msg.current_step_index || 0), msg.total_steps || plannedSteps.length)
  renderPlanList()
  btnNext.disabled = true
}

function handleWsMessage (msg) {
  if (!msg || !msg.event) return
  if (msg.session_id) {
    sessionId = msg.session_id
  }

  switch (msg.event) {
    case 'plan.ready':
      handlePlanReady(msg)
      break

    case 'plan.step':
      enterRunningState()
      applyCurrentStep(msg)
      break

    case 'guide.highlight':
      ensureInteractiveShell()
      show(elStepCard)
      hide(elWaiting)
      elTooltip.textContent = msg.tooltip || ''
      btnNext.disabled = false
      btnNext.textContent = 'Next'
      if (msg.require_manual_next) {
        uiState = 'checkpoint_wait'
        setStatus('checkpoint_wait', 'Awaiting confirmation')
      } else {
        uiState = 'running'
        setStatus('running', 'Guiding')
      }
      break

    case 'guide.wait_manual':
      ensureInteractiveShell()
      uiState = 'checkpoint_wait'
      setStatus('checkpoint_wait', 'Awaiting confirmation')
      elWaitingText.textContent = msg.tooltip || 'Finish the current action, then continue.'
      show(elWaiting)
      btnNext.disabled = false
      btnNext.textContent = 'Next'
      break

    case 'session.done':
      switchToDone(msg.summary)
      break

    case 'session.error':
      ensureInteractiveShell()
      show(elStepCard)
      hide(elWaiting)
      elTooltip.textContent = `Hint: ${msg.message || 'Unknown error'}`
      if (msg.recoverable) {
        uiState = 'recovering'
        setStatus('recovering', 'Recovering')
        show(btnNext)
        btnNext.disabled = false
        btnNext.textContent = 'Retry'
      } else {
        uiState = 'blocked'
        setStatus('blocked', 'Blocked')
        hide(btnNext)
        hide(btnComplete)
      }
      break

    default:
      console.warn('[capsule] unhandled event', msg.event)
  }
}

async function resolveCurrentWindowContext () {
  const ctx = await window.electronAPI.invoke('ipc:get-active-window')
  currentWindowCtx = isValidWindowContext(ctx) ? ctx : null
  currentCaptureError = currentWindowCtx ? '' : RETRY_HINT
  renderWindowContextFeedback()
  return currentWindowCtx
}

btnStart.addEventListener('click', async () => {
  const goal = elGoalInput.value.trim()
  if (!goal) {
    elGoalInput.focus()
    elGoalInput.style.borderColor = '#f05050'
    setTimeout(() => { elGoalInput.style.borderColor = '' }, 1500)
    return
  }

  const startContext = isValidWindowContext(currentWindowCtx) ? currentWindowCtx : null
  currentCaptureError = ''
  renderWindowContextFeedback()
  sessionId = `s-local-${simpleId()}`
  switchToPlanning(goal, sessionId)

  window.electronAPI.send('session:start', {
    goal,
    session_id: sessionId,
    captured_context: startContext
  })
})

btnNext.addEventListener('click', () => {
  if (btnNext.disabled || !sessionId) return

  btnNext.disabled = true
  hide(elWaiting)

  if (uiState === 'recovering') {
    window.electronAPI.send('session:recover', {
      session_id: sessionId,
      trace_id: simpleId(),
      recovery_action: 'step_retarget'
    })
    return
  }

  window.electronAPI.send('session:next', {
    session_id: sessionId,
    trace_id: simpleId()
  })
})

btnComplete.addEventListener('click', () => {
  if (!sessionId) return

  btnComplete.disabled = true
  window.electronAPI.send('session:complete', {
    session_id: sessionId,
    trace_id: simpleId()
  })
})

btnRestart.addEventListener('mouseenter', (event) => {
  lastPointerPosition = { x: event.clientX || 0, y: event.clientY || 0 }
  scheduleRestartTooltip()
})

btnRestart.addEventListener('mousemove', (event) => {
  lastPointerPosition = { x: event.clientX || 0, y: event.clientY || 0 }
  if (!elRestartTooltip.classList.contains('hidden')) {
    updateRestartTooltipPosition(lastPointerPosition.x, lastPointerPosition.y)
  }
})

btnRestart.addEventListener('mouseleave', () => {
  hideRestartTooltip()
})

btnRestart.addEventListener('click', () => {
  switchToDraft({ preserveGoal: true, preserveContext: true })
})

elGoalInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') btnStart.click()
})

window.electronAPI.on('ipc:ws-message', handleWsMessage)

window.electronAPI.on('ipc:ws-status', ({ status }) => {
  if (uiState === 'draft' || uiState === 'done' || uiState === 'blocked') {
    return
  }

  if (status === 'connected') {
    setStatus('connected', 'Connected')
  } else if (status === 'reconnecting') {
    setStatus('planning', 'Reconnecting')
  } else if (status === 'disconnected') {
    setStatus('error', 'Disconnected')
    if (uiState !== 'planning') {
      show(btnNext)
      btnNext.disabled = false
    }
    show(btnComplete)
    btnComplete.disabled = false
  }
})

window.electronAPI.on('ipc:shortcut-triggered', (payload) => {
  if (!payload || payload.accelerator !== 'F9') return

  const feedback = getShortcutCaptureFeedback(payload)

  if (isValidWindowContext(payload.captured_context)) {
    currentWindowCtx = payload.captured_context
    currentCaptureError = ''
  } else if (!payload.error) {
    window.electronAPI.invoke('ipc:get-active-window').then((ctx) => {
      currentWindowCtx = isValidWindowContext(ctx) ? ctx : null
      currentCaptureError = currentWindowCtx ? '' : RETRY_HINT
      renderWindowContextFeedback()
    }).catch(() => {
      currentWindowCtx = null
      currentCaptureError = RETRY_HINT
      renderWindowContextFeedback()
    })
  } else {
    currentWindowCtx = null
    currentCaptureError = feedback ? feedback.detailText : RETRY_HINT
  }

  if (feedback) {
    setStatus(feedback.statusState, feedback.statusText)
  } else {
    setDraftStatus()
  }

  renderWindowContextFeedback()

  if (uiState === 'draft') {
    elGoalInput.focus()
  }
})

switchToDraft({ preserveGoal: false, preserveContext: false })
void resolveCurrentWindowContext()
