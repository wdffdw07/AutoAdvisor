// Services/WindowTracker.cs
// 职责：负责查找剪映窗口句柄并返回其物理像素矩形。
//       未来可扩展为定时轮询、窗口跟随移动等能力。
using System.Diagnostics;
using CopilotClient.Core;

namespace CopilotClient.Services;

public class WindowTracker
{
    /// <summary>
    /// 查找剪映窗口并返回其屏幕物理像素矩形。
    /// </summary>
    /// <returns>RECT（物理像素），如果未找到则 Width/Height 均为 0。</returns>
    public RECT GetCapCutRect()
    {
        nint hWnd = FindCapCutWindow();
        if (hWnd == nint.Zero)
            return default;

        Win32Api.GetWindowRect(hWnd, out RECT rect);
        return rect;
    }

    /// <summary>返回剪映窗口句柄，找不到时返回 nint.Zero。</summary>
    public nint FindCapCutWindow()
    {
        // 遍历所有匹配进程，从以下两个来源收集候选句柄：
        //   A. proc.MainWindowHandle（.NET 自动找到进程主窗口，可靠）
        //   B. EnumWindows 枚举该进程所有顶层可见窗口（兜底）
        // 最终取面积最大的那个句柄。
        //
        // ⚠️  剪映会启动 10+ 个子进程，必须遍历全部而不是 break 在第一个。
        //     FindWindow 在剪映上会返回 NULL（可能是虚拟桌面 cloak 问题），
        //     因此放弃 Tier-1 FindWindow。

        nint bestHWnd = nint.Zero;
        int  bestArea = 0;

        var targetPids = new System.Collections.Generic.HashSet<uint>();

        foreach (var proc in Process.GetProcesses())
        {
            try
            {
                if (!proc.ProcessName.Contains("jianying", StringComparison.OrdinalIgnoreCase) &&
                    !proc.ProcessName.Contains("capcut",   StringComparison.OrdinalIgnoreCase))
                    continue;

                targetPids.Add((uint)proc.Id);

                // A. .NET MainWindowHandle
                nint mwh = proc.MainWindowHandle;
                if (mwh != nint.Zero)
                {
                    Win32Api.GetWindowRect(mwh, out RECT mr);
                    int ma = mr.Width * mr.Height;
                    if (ma > bestArea) { bestArea = ma; bestHWnd = mwh; }
                }
            }
            catch { }
        }

        if (targetPids.Count == 0) return nint.Zero;

        // B. EnumWindows 枚举（兜底，补捉 MainWindowHandle 为 0 的进程里的大窗口）
        Win32Api.EnumWindows((hwnd, _) =>
        {
            Win32Api.GetWindowThreadProcessId(hwnd, out uint pid);
            if (!targetPids.Contains(pid)) return true;
            if (!Win32Api.IsWindowVisible(hwnd)) return true;
            if (Win32Api.IsIconic(hwnd)) return true;

            Win32Api.GetWindowRect(hwnd, out RECT r);
            int area = r.Width * r.Height;
            if (area > bestArea) { bestArea = area; bestHWnd = hwnd; }
            return true;
        }, nint.Zero);

        return bestHWnd;
    }

    /// <summary>判断剪映是否当前处于前台可见状态。</summary>
    public bool IsCapCutVisible()
    {
        nint hWnd = FindCapCutWindow();
        if (hWnd == nint.Zero) return false;
        Win32Api.GetWindowRect(hWnd, out RECT r);
        return r.Width > 0 && r.Height > 0;
    }
}
