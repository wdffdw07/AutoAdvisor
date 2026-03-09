/**
 * capsule.js — 胶囊 UI 渲染器逻辑
 *
 * 处理来自 Main 进程的协议消息（ipc:ws-message）并驱动 UI 状态机。
 * UI 状态：idle → running → waiting_manual → running → done
 *
 * 符合协议 03_ws_ipc_protocol_v1.md §A S->C 事件。
 */

'use strict'

/* ── DOM 引用 ────────────────────────────────────────────────────────────── */
const elStatus       = document.getElementById('statusBadge')
const elGoalSection  = document.getElementById('goalSection')
const elGoalInput    = document.getElementById('goalInput')
const elGoalDisplay  = document.getElementById('goalDisplay')
const elGoalText     = document.getElementById('goalDisplayText')
const elProgressSec  = document.getElementById('progressSection')
const elProgressFill = document.getElementById('progressFill')
const elProgressLbl  = document.getElementById('progressLabel')
const elStepCard     = document.getElementById('stepCard')
const elActionBadge  = document.getElementById('stepActionBadge')
const elDescription  = document.getElementById('stepDescription')
const elTooltip      = document.getElementById('stepTooltip')
const elReason       = document.getElementById('stepReason')
const elWaiting      = document.getElementById('waitingIndicator')
const elWaitingText  = document.getElementById('waitingText')
const elDoneCard     = document.getElementById('doneCard')
const elDoneSummary  = document.getElementById('doneSummary')
const btnStart       = document.getElementById('btnStart')
const btnNext        = document.getElementById('btnNext')
const btnReset       = document.getElementById('btnReset')

/* ── 会话状态 ────────────────────────────────────────────────────────────── */
let sessionId   = null
let totalSteps  = 0
let currentStep = 0
let uiState     = 'idle'   // idle | running | waiting_manual | done

/* ── 辅助函数 ────────────────────────────────────────────────────────────── */
function show (el) { el.classList.remove('hidden') }
function hide (el) { el.classList.add('hidden') }

function setStatus (state, label) {
  elStatus.className = `status-badge ${state}`
  elStatus.textContent = label
}

/** 动作类型 → 显示文本 + CSS 类名 */
const ACTION_MAP = {
  click:      { label: '点击',   cls: 'click'      },
  drag:       { label: '拖拽',   cls: 'drag'        },
  input_text: { label: '输入',   cls: 'input_text'  },
  scroll:     { label: '滚动',   cls: 'scroll'      },
  wait:       { label: '等待',   cls: 'wait'        },
  complete:   { label: '完成',   cls: 'click'       }
}

function simpleId () {
  return Math.random().toString(36).slice(2)
}

/* ── 状态切换函数 ────────────────────────────────────────────────────────── */
function switchToIdle () {
  uiState = 'idle'
  setStatus('idle', '空闲')
  show(elGoalSection);   elGoalInput.value = ''
  hide(elGoalDisplay);   hide(elProgressSec)
  hide(elStepCard);      hide(elWaiting);      hide(elDoneCard)
  show(btnStart);        hide(btnNext);         hide(btnReset)
  sessionId   = null
  totalSteps  = 0
  currentStep = 0
}

function switchToRunning (goal, sid) {
  uiState = 'running'
  sessionId = sid
  setStatus('running', '引导中')
  hide(elGoalSection)
  elGoalText.textContent = goal;    show(elGoalDisplay)
  show(elProgressSec)
  hide(elStepCard);  hide(elWaiting);  hide(elDoneCard)
  hide(btnStart);    show(btnNext);    btnNext.disabled = true
  show(btnReset)
}

function switchToDone (summary) {
  uiState = 'done'
  setStatus('done', '完成')
  hide(elStepCard);  hide(elWaiting);  hide(elProgressSec)
  elDoneSummary.textContent = summary || '引导完成！'
  show(elDoneCard)
  hide(btnNext);  show(btnReset)
}

/* ── 进度更新 ────────────────────────────────────────────────────────────── */
function updateProgress (step, total) {
  currentStep = step
  totalSteps  = total
  const pct   = total > 0 ? Math.round((step / total) * 100) : 0
  elProgressFill.style.width = pct + '%'
  elProgressLbl.textContent  = `${step}/${total}`
}

/* ── 协议消息处理器 ──────────────────────────────────────────────────────── */
function handleWsMessage (msg) {
  console.log('[capsule] ipc:ws-message', msg.event, msg.step_id || '')

  switch (msg.event) {
    case 'plan.step': {
      updateProgress(
        parseInt(msg.step_id?.replace('s-', '') || 1, 10),
        msg.total_steps || 0
      )

      // 更新动作徽章
      const act = ACTION_MAP[msg.action] || { label: msg.action, cls: 'click' }
      elActionBadge.textContent = act.label
      elActionBadge.className   = `step-action-badge ${act.cls}`

      // 更新描述
      elDescription.textContent = msg.description || ''

      // 原因文字（可折叠，仅调试用，正式环境隐藏）
      if (msg.reason) {
        elReason.textContent = msg.reason
        show(elReason)
      } else {
        hide(elReason)
      }

      // tooltip 先清空，等 guide 事件填入
      elTooltip.textContent = ''
      hide(elWaiting)
      show(elStepCard)
      btnNext.disabled = true
      break
    }

    case 'guide.highlight': {
      elTooltip.textContent = msg.tooltip || ''
      // 离散动作：立即启用"下一步"
      if (!msg.require_manual_next) {
        btnNext.disabled = false
      }
      break
    }

    case 'guide.wait_manual': {
      // 连续动作：显示等待提示，启用"下一步"供用户手动推进
      elTooltip.textContent     = ''
      elWaitingText.textContent = msg.tooltip || '请完成操作后点击下一步'
      show(elWaiting)
      btnNext.disabled = false
      break
    }

    case 'session.done': {
      switchToDone(msg.summary)
      break
    }

    case 'session.error': {
      setStatus('error', '出错')
      elTooltip.textContent = `⚠ ${msg.message || '未知错误'}`
      if (msg.recoverable) {
        btnNext.disabled = false
        btnNext.textContent = '重试'
      } else {
        hide(btnNext)
      }
      break
    }

    default:
      console.warn('[capsule] 未处理事件:', msg.event)
  }
}

/* ── 按钮事件 ────────────────────────────────────────────────────────────── */
btnStart.addEventListener('click', () => {
  const goal = elGoalInput.value.trim()
  if (!goal) {
    elGoalInput.focus()
    elGoalInput.style.borderColor = '#f05050'
    setTimeout(() => { elGoalInput.style.borderColor = '' }, 1500)
    return
  }

  sessionId = 's-mock-' + simpleId()
  switchToRunning(goal, sessionId)

  window.electronAPI.send('mock:start', {
    goal,
    session_id: sessionId
  })
})

btnNext.addEventListener('click', () => {
  if (btnNext.disabled) return
  btnNext.disabled = true
  btnNext.textContent = '下一步 →'
  hide(elWaiting)

  window.electronAPI.send('user:next', {
    session_id: sessionId,
    trace_id:   simpleId()
  })
})

btnReset.addEventListener('click', () => { switchToIdle() })

/* ── Enter 键快速开始 ───────────────────────────────────────────────────── */
elGoalInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') btnStart.click()
})

/* ── 监听 Main 进程消息 ─────────────────────────────────────────────────── */
window.electronAPI.on('ipc:ws-message', handleWsMessage)

window.electronAPI.on('ipc:ws-status', ({ status }) => {
  console.log('[capsule] ws-status:', status)
  if (status === 'connected' && uiState === 'running') {
    setStatus('connected', '已连接')
  }
})

window.electronAPI.on('ipc:shortcut-triggered', ({ accelerator }) => {
  console.log('[capsule] shortcut:', accelerator)
  // F9：焦点切换到输入框
  if (accelerator === 'F9' && uiState === 'idle') {
    elGoalInput.focus()
  }
})

/* ── 初始化 ─────────────────────────────────────────────────────────────── */
switchToIdle()
