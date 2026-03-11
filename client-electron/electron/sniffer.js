/**
 * sniffer.js — 系统能力层（Step3 实装）
 *
 * 提供 getActiveWindow() 与 captureRegion() 两个能力，
 * 仅在 Main 进程调用，全程通过 PowerShell 调用 Win32 / .NET API，
 * 无需额外 npm 依赖，符合 05_agent_constraints.md §1 禁止引入大型依赖。
 *
 * Step4 Context Sniffer 升级时可替换为 ffi-napi 原生绑定以提升性能。
 *
 * 坐标系：物理像素，window_box = [x, y, width, height]，
 * 原点为主显示器左上角（符合协议 §D 坐标规则）。
 */

'use strict'

const { execFile } = require('child_process')

// ─────────────────────────────────────────────────────────────────────────────
// 内部工具：运行 PowerShell 脚本并返回 stdout 字符串
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @param {string} script   单行或多行 PowerShell 脚本
 * @param {number} [timeout=12000]  超时毫秒
 * @returns {Promise<string>}  stdout（已 trim）
 */
function runPowershell (script, timeout = 12000) {
  return new Promise((resolve, reject) => {
    execFile(
      'powershell.exe',
      [
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy', 'Bypass',
        '-Command', script
      ],
      { timeout, encoding: 'utf8', windowsHide: true },
      (err, stdout, stderr) => {
        if (err) return reject(new Error((stderr || '').trim() || err.message))
        resolve(stdout.trim())
      }
    )
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// getActiveWindow
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 获取当前前台活跃窗口的元数据。
 *
 * 调用时序说明：
 *   应在目标软件仍处于前台时调用（如 F9 全局快捷键触发后立即调用）。
 *   若调用时 Electron 窗口已获焦，返回的 process_name 将是 Electron 自身。
 *
 * @returns {Promise<{
 *   process_name: string,
 *   window_title: string,
 *   window_box: [number, number, number, number],
 *   dpi_scale: number
 * }>}
 */
async function getActiveWindow () {
  const script = `
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinApi {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr h, ref RECT r);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")]
    public static extern int GetWindowThreadProcessId(IntPtr h, ref int wpid);
    [DllImport("user32.dll")]
    public static extern uint GetDpiForWindow(IntPtr h);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int L, T, R, B; }
}
"@
$h  = [WinApi]::GetForegroundWindow()
$r  = New-Object WinApi+RECT
[WinApi]::GetWindowRect($h, [ref]$r) | Out-Null
$sb = New-Object System.Text.StringBuilder(512)
[WinApi]::GetWindowText($h, $sb, 512) | Out-Null
$wpid = 0
[WinApi]::GetWindowThreadProcessId($h, [ref]$wpid) | Out-Null
$dpi = [WinApi]::GetDpiForWindow($h)
if ($dpi -eq 0) { $dpi = 96 }
try { $pn = (Get-Process -Id $wpid -ErrorAction Stop).MainModule.ModuleName }
catch { $pn = "unknown.exe" }
[ordered]@{
    process_name = $pn
    window_title = $sb.ToString()
    left         = $r.L
    top          = $r.T
    width        = $r.R - $r.L
    height       = $r.B - $r.T
    dpi_scale    = [math]::Round($dpi / 96.0, 2)
} | ConvertTo-Json -Compress`

  let raw
  try {
    raw = await runPowershell(script)
  } catch (err) {
    throw new Error(`getActiveWindow failed: ${err.message}`)
  }

  let obj
  try {
    obj = JSON.parse(raw)
  } catch (err) {
    throw new Error(`getActiveWindow: invalid JSON from PowerShell: ${raw.slice(0, 200)}`)
  }

  return {
    process_name: obj.process_name || 'unknown.exe',
    window_title: obj.window_title || '',
    window_box:   [
      Number(obj.left),
      Number(obj.top),
      Number(obj.width),
      Number(obj.height)
    ],
    dpi_scale: Number(obj.dpi_scale) || 1.0
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// captureRegion
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 截取屏幕的指定矩形区域，返回 JPEG base64 字符串（无前缀）。
 * 坐标为物理像素，原点为主显示器左上角（符合协议 §D window_box 定义）。
 *
 * @param {[number, number, number, number]} windowBox  [x, y, width, height]
 * @param {number} [quality=80]  JPEG 质量 1-100
 * @returns {Promise<string>}  base64 JPEG
 */
async function captureRegion (windowBox, quality = 80) {
  const [x, y, w, h] = windowBox.map(Number)
  if (w <= 0 || h <= 0) {
    throw new Error(`captureRegion: invalid windowBox ${JSON.stringify(windowBox)}`)
  }

  const script = `
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bmp = New-Object System.Drawing.Bitmap(${w}, ${h})
$gr  = [System.Drawing.Graphics]::FromImage($bmp)
$gr.CopyFromScreen(${x}, ${y}, 0, 0, (New-Object System.Drawing.Size(${w}, ${h})))
$gr.Dispose()
$enc = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
       Where-Object { $_.FormatDescription -eq 'JPEG' } |
       Select-Object -First 1
$ep  = New-Object System.Drawing.Imaging.EncoderParameters(1)
$ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter(
    [System.Drawing.Imaging.Encoder]::Quality, [long]${quality})
$ms  = New-Object System.IO.MemoryStream
$bmp.Save($ms, $enc, $ep)
$bmp.Dispose()
[Convert]::ToBase64String($ms.ToArray())`

  let base64
  try {
    base64 = await runPowershell(script, 20000)
  } catch (err) {
    throw new Error(`captureRegion failed: ${err.message}`)
  }

  // 去除换行符等空白，返回纯 base64 字符串
  return base64.replace(/\s+/g, '')
}

module.exports = { getActiveWindow, captureRegion }
