// Core/Win32Api.cs
// 职责：纯 P/Invoke 签名仓库。
//       只放 Win32 结构体、常量和 DllImport。不写任何业务逻辑。
using System.Runtime.InteropServices;

namespace CopilotClient.Core;

// ─── 结构体 ──────────────────────────────────────────────────────────────────

/// <summary>Win32 窗口矩形（物理像素）。</summary>
[StructLayout(LayoutKind.Sequential)]
public struct RECT
{
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;

    public int Width  => Right  - Left;
    public int Height => Bottom - Top;
}

/// <summary>鼠标/键盘消息用的 POINT。</summary>
[StructLayout(LayoutKind.Sequential)]
public struct POINT { public int X; public int Y; }

// ─── 常量 ────────────────────────────────────────────────────────────────────

public static class WinMsg
{
    public const int WM_HOTKEY     = 0x0312;
    public const int WM_NCHITTEST  = 0x0084;
}

public static class HitTest
{
    public const int HTCLIENT      =  1;   // 客户区（可交互）
    public const int HTTRANSPARENT = -1;   // 透明穿透（事件传递给下层窗口）
}

public static class WinExStyle
{
    public const int GWL_EXSTYLE       = -20;
    public const int WS_EX_LAYERED     = 0x00080000;  // 允许透明/分层渲染
    public const int WS_EX_TRANSPARENT = 0x00000020;  // 穿透：鼠标事件传递给下层窗口
    public const int WS_EX_TOOLWINDOW  = 0x00000080;  // 不在任务栏显示
    public const int WS_EX_TOPMOST     = 0x00000008;
    public const long WS_EX_NOACTIVATE = 0x08000000;  // 不抢焦点
}

// ─── 函数签名 ─────────────────────────────────────────────────────────────────

public static class Win32Api
{
    // 查找窗口句柄（按类名或标题）
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern nint FindWindow(string? lpClassName, string? lpWindowName);

    // 获取窗口在屏幕上的物理像素矩形
    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetWindowRect(nint hWnd, out RECT lpRect);

    // 读取/设置窗口扩展样式
    [DllImport("user32.dll", SetLastError = true)]
    public static extern int  GetWindowLong(nint hWnd, int nIndex);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern int  SetWindowLong(nint hWnd, int nIndex, int dwNewLong);

    // 注册/注销全局热键（不使用 Hook，只监听 WM_HOTKEY）
    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool RegisterHotKey(nint hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool UnregisterHotKey(nint hWnd, int id);

    // 将屏幕坐标转换为窗口客户区坐标
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ScreenToClient(nint hWnd, ref POINT lpPoint);

    // 枚举所有顶层窗口
    public delegate bool EnumWindowsProc(nint hWnd, nint lParam);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, nint lParam);

    // 判断窗口是否可见
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(nint hWnd);

    // 判断窗口是否已最小化
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsIconic(nint hWnd);

    // 获取窗口标题文字
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(nint hWnd, System.Text.StringBuilder lpString, int nMaxCount);

    // 获取窗口所属进程 ID
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(nint hWnd, out uint lpdwProcessId);

    // 读取低 16 位 / 高 16 位（NCHITTEST 消息解包用）
    public static int  LoWord(nint lParam) => (int)(lParam & 0xFFFF);
    public static int  HiWord(nint lParam) => (int)((lParam >> 16) & 0xFFFF);
}
