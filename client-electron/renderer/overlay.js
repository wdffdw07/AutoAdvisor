/**
 * overlay.js — 透明叠加层渲染器逻辑
 *
 * 监听来自 Main 进程的 overlay:show / overlay:hide 指令，
 * 在对应绝对坐标处渲染带呼吸灯动效的高亮标注框与工具提示。
 *
 * abs_box 格式：[x, y, width, height]（物理像素，全局屏幕坐标）
 * 已由 main.js 基于 window_box + relative_box 完成坐标变换。
 */

'use strict'

const elHighlight = document.getElementById('highlight')
const elTooltip   = document.getElementById('tooltip')
const elTipText   = document.getElementById('tooltipText')
const elConfBadge = document.getElementById('confidenceBadge')

const TOOLTIP_MARGIN = 10   // 高亮框与 tooltip 之间的间距（px）
const SCREEN_PADDING = 12   // tooltip 距屏幕边缘最小距离（px）

/**
 * 将高亮框定位到给定的绝对坐标矩形
 * @param {number[]} absBox  [x, y, width, height]
 */
function positionHighlight (absBox) {
  const [x, y, w, h] = absBox
  elHighlight.style.left   = x + 'px'
  elHighlight.style.top    = y + 'px'
  elHighlight.style.width  = w + 'px'
  elHighlight.style.height = h + 'px'
}

/**
 * 将 tooltip 定位在高亮框旁（优先显示在下方，空间不足则在上方）
 * @param {number[]} absBox
 * @param {string}   tooltipText
 */
function positionTooltip (absBox, tooltipText) {
  const [x, y, w, h] = absBox
  elTipText.textContent = tooltipText

  // 先让 tooltip 短暂可见以测量尺寸
  elTooltip.style.display    = 'block'
  elTooltip.style.visibility = 'hidden'

  const tipW = elTooltip.offsetWidth
  const tipH = elTooltip.offsetHeight

  // 水平：以高亮框左侧为基准，超出屏幕则右对齐
  let tipX = x
  if (tipX + tipW + SCREEN_PADDING > window.innerWidth) {
    tipX = Math.max(SCREEN_PADDING, x + w - tipW)
  }

  // 垂直：默认在框的下方，空间不足则在上方
  let tipY = y + h + TOOLTIP_MARGIN
  if (tipY + tipH + SCREEN_PADDING > window.innerHeight) {
    tipY = y - tipH - TOOLTIP_MARGIN
  }

  elTooltip.style.left       = tipX + 'px'
  elTooltip.style.top        = tipY + 'px'
  elTooltip.style.visibility = 'visible'
}

/** 显示高亮框与 tooltip */
function showOverlay (cmd) {
  const { abs_box: absBox, tooltip, confidence } = cmd

  if (!absBox || absBox.length < 4) {
    console.warn('[overlay] abs_box 缺失，跳过')
    return
  }

  positionHighlight(absBox)

  if (confidence != null) {
    elConfBadge.textContent  = `${Math.round(confidence * 100)}%`
    elConfBadge.style.display = 'inline'
  } else {
    elConfBadge.style.display = 'none'
  }

  elHighlight.style.display = 'block'

  if (tooltip) {
    positionTooltip(absBox, tooltip)
  } else {
    elTooltip.style.display = 'none'
  }
}

/** 隐藏高亮框与 tooltip */
function hideOverlay () {
  elHighlight.style.display = 'none'
  elTooltip.style.display   = 'none'
}

/* ── 监听 Main 进程指令 ─────────────────────────────────────────────────── */
window.electronAPI.on('overlay:show', (cmd) => {
  console.log('[overlay] show', cmd.abs_box)
  showOverlay(cmd)
})

window.electronAPI.on('overlay:hide', () => {
  console.log('[overlay] hide')
  hideOverlay()
})

/* ── 初始化（隐藏状态） ─────────────────────────────────────────────────── */
hideOverlay()
