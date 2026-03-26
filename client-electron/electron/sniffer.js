'use strict'

const { execFile } = require('child_process')

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
        if (err) {
          return reject(new Error((stderr || '').trim() || err.message))
        }
        resolve(stdout.trim())
      }
    )
  })
}

function parseWindowInfo (raw, sourceName) {
  let obj
  try {
    obj = JSON.parse(raw)
  } catch (err) {
    throw new Error(`${sourceName}: invalid JSON from PowerShell: ${raw.slice(0, 200)}`)
  }

  return {
    process_name: obj.process_name || 'unknown.exe',
    window_title: obj.window_title || '',
    window_box: [
      Number(obj.left),
      Number(obj.top),
      Number(obj.width),
      Number(obj.height)
    ],
    dpi_scale: Number(obj.dpi_scale) || 1.0
  }
}

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

  return parseWindowInfo(raw, 'getActiveWindow')
}

async function getWindowAtCursor () {
  const script = `
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinApi {
    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT pt);
    [DllImport("user32.dll")]
    public static extern IntPtr WindowFromPoint(POINT pt);
    [DllImport("user32.dll")]
    public static extern IntPtr GetAncestor(IntPtr hWnd, uint gaFlags);
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
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }
}
"@
$pt = New-Object WinApi+POINT
[WinApi]::GetCursorPos([ref]$pt) | Out-Null
$h = [WinApi]::WindowFromPoint($pt)
if ($h -eq [IntPtr]::Zero) { throw "window under cursor not found" }
$h = [WinApi]::GetAncestor($h, 2)
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
    throw new Error(`getWindowAtCursor failed: ${err.message}`)
  }

  return parseWindowInfo(raw, 'getWindowAtCursor')
}

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

  return base64.replace(/\s+/g, '')
}

module.exports = {
  getActiveWindow,
  getWindowAtCursor,
  captureRegion
}
