/**
 * mock.js — Step2 Mock 数据与会话编排
 *
 * 模拟服务端双 Agent 下发的完整引导序列（3 步 Photoshop 高斯模糊场景）。
 * 坐标系：仿真一个窗口 window_box=[100,50,1400,900]，dpi_scale=1.0
 *
 * 符合协议 03_ws_ipc_protocol_v1.md §A S->C 事件格式。
 */

'use strict'

const { v4: uuidv4 } = (() => {
  // 内联简易 UUID v4（避免 npm 依赖）
  function uuidv4 () {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0
      const v = c === 'x' ? r : (r & 0x3 | 0x8)
      return v.toString(16)
    })
  }
  return { v4: uuidv4 }
})()

// 仿真目标软件窗口在主屏上的位置（物理像素，dpi_scale=1.0）
const MOCK_WINDOW_BOX = [100, 50, 1400, 900]
const MOCK_DPI_SCALE  = 1.0

/**
 * 根据 relative_box + window_box 计算叠加层所需的绝对位置
 * 返回 [abs_x, abs_y, width, height]
 */
function toAbsBox (relBox) {
  return [
    MOCK_WINDOW_BOX[0] + relBox[0],
    MOCK_WINDOW_BOX[1] + relBox[1],
    relBox[2],
    relBox[3]
  ]
}

/** 3 步 Mock 步骤定义 */
const MOCK_STEPS = [
  {
    plan: {
      protocol_version: 'v1',
      event: 'plan.step',
      step_id: 's-001',
      total_steps: 3,
      action: 'click',
      description: '点击顶部【滤镜】菜单',
      reason: 'Photoshop 高斯模糊入口在 滤镜 → 模糊 → 高斯模糊'
    },
    guide: {
      protocol_version: 'v1',
      event: 'guide.highlight',
      step_id: 's-001',
      target: { relative_box: [540, 28, 58, 22], confidence: 0.95 },
      tooltip: '点击【滤镜】菜单',
      require_manual_next: false
    }
  },
  {
    plan: {
      protocol_version: 'v1',
      event: 'plan.step',
      step_id: 's-002',
      total_steps: 3,
      action: 'click',
      description: '悬停【模糊】→ 点击【高斯模糊】',
      reason: '在滤镜下拉菜单中展开模糊子菜单，选择高斯模糊'
    },
    guide: {
      protocol_version: 'v1',
      event: 'guide.highlight',
      step_id: 's-002',
      target: { relative_box: [555, 280, 132, 24], confidence: 0.92 },
      tooltip: '点击【模糊 → 高斯模糊】',
      require_manual_next: false
    }
  },
  {
    plan: {
      protocol_version: 'v1',
      event: 'plan.step',
      step_id: 's-003',
      total_steps: 3,
      action: 'drag',
      description: '在对话框中拖动【半径】滑块，完成后点击确定',
      reason: '高斯模糊对话框要求手动拖拽设置模糊程度，属于连续动作'
    },
    guide: {
      protocol_version: 'v1',
      event: 'guide.wait_manual',
      step_id: 's-003',
      tooltip: '请拖动"半径"滑块调整模糊程度，然后点击【确定】，完成后点击下一步'
    }
  }
]

const MOCK_DONE = {
  protocol_version: 'v1',
  event: 'session.done',
  summary: '已完成：为当前图层添加了高斯模糊效果 ✓'
}

/**
 * MockSession — 持有单次会话状态，驱动步骤编排。
 *
 * @param {object} opts
 * @param {string} opts.goal         用户输入的目标文字
 * @param {string} opts.sessionId    会话 ID
 * @param {function} opts.onMessage  每条下发消息的回调 (msg) => void
 * @param {function} opts.onOverlay  下发叠加层指令的回调 (instruction) => void
 */
class MockSession {
  constructor ({ goal, sessionId, onMessage, onOverlay }) {
    this.goal      = goal
    this.sessionId = sessionId || uuidv4()
    this.onMessage = onMessage
    this.onOverlay = onOverlay
    this.stepIndex = -1
    this.finished  = false
  }

  /** 注入 session_id 与 trace_id 到消息 */
  _stamp (msg) {
    return {
      ...msg,
      session_id: this.sessionId,
      trace_id:   uuidv4()
    }
  }

  /** 计算叠加层绝对坐标指令 */
  _buildOverlayCmd (guide) {
    if (guide.event === 'guide.highlight') {
      const absBox = toAbsBox(guide.target.relative_box)
      return {
        visible:    true,
        abs_box:    absBox,
        tooltip:    guide.tooltip,
        confidence: guide.target.confidence
      }
    }
    // guide.wait_manual — 隐藏高亮框
    return { visible: false, tooltip: guide.tooltip }
  }

  /** 开始第一步 */
  start () {
    this.stepIndex = 0
    this._dispatchStep()
  }

  /** 用户点击"下一步"时推进 */
  next () {
    if (this.finished) return
    this.stepIndex++
    if (this.stepIndex >= MOCK_STEPS.length) {
      this._dispatchDone()
    } else {
      this._dispatchStep()
    }
  }

  _dispatchStep () {
    const step = MOCK_STEPS[this.stepIndex]
    // 先发 plan.step，再发 guide
    this.onMessage(this._stamp(step.plan))
    // 小延迟模拟网络往返
    setTimeout(() => {
      this.onMessage(this._stamp(step.guide))
      this.onOverlay(this._buildOverlayCmd(step.guide))
    }, 300)
  }

  _dispatchDone () {
    this.finished = true
    this.onOverlay({ visible: false })
    this.onMessage(this._stamp(MOCK_DONE))
  }
}

module.exports = { MockSession, MOCK_STEPS }
