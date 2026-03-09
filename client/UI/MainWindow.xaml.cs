// UI/MainWindow.xaml.cs
// 职责：覆盖层 UI 交互逻辑
//   - 注册 F9 热键 (RegisterHotKey + WM_HOTKEY，无全局钩子)
//   - 穿透切换：默认 WS_EX_TRANSPARENT（全穿透），AI 响应时关闭穿透使按钮可点击
//   - DispatcherTimer 每 100ms 跟随剪映窗口，实时更新黄框/Tooltip 位置
//   - DPI 物理像素 ↔ WPF 逻辑像素换算
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using CopilotClient.Core;
using CopilotClient.Services;

namespace CopilotClient.UI;

public partial class MainWindow : Window
{
    // ─── 热键 ID ─────────────────────────────────────────────────────────────
    private const int  HotkeyId = 9001;
    private const uint VK_F9    = 0x78;
    private const uint MOD_NONE = 0x0000;

    // ─── 服务层实例 ───────────────────────────────────────────────────────────
    private readonly WindowTracker   _tracker = new();
    private readonly ScreenCapture   _capture = new();
    private readonly WsClientService _ws      = new();

    // ─── WndProc Hook ─────────────────────────────────────────────────────────
    private HwndSource? _hwndSource;

    // ─── DPI 缩放因子 ─────────────────────────────────────────────────────────
    private double _dpiScaleX = 1.0;
    private double _dpiScaleY = 1.0;

    // ─── 覆盖窗口物理像素起点（多显示器支持）────────────────────────────────
    private int _overlayPhysLeft;
    private int _overlayPhysTop;

    // ─── 最后捕获的剪映窗口物理矩形 ─────────────────────────────────────────
    private RECT _lastCapCutRect;

    // ─── 当前任务目标 ─────────────────────────────────────────────────────────
    private string _currentTask = "添加一个老电视特效";

    // ─── 标注元素（直接引用，避免 Timer 重建）────────────────────────────────
    private Rectangle? _highlightRect;
    private Border?    _tooltipLabel;

    // ─── 最后一次 AI 返回的 box（物理像素，相对于剪映截图左上角）──────────
    private int[]?  _lastBox;
    private string? _lastTooltip;

    // ─── 黄框跟随定时器（每 100ms 轮询剪映窗口位置）─────────────────────────
    private readonly DispatcherTimer _followTimer = new()
    {
        Interval = TimeSpan.FromMilliseconds(100)
    };

    public MainWindow()
    {
        InitializeComponent();
        SourceInitialized += OnSourceInitialized;
        Loaded            += OnLoaded;
        Closed            += OnClosed;

        _followTimer.Tick += FollowTimer_Tick;
        _followTimer.Start();
    }

    // ─── 初始化 ───────────────────────────────────────────────────────────────

    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        _hwndSource = HwndSource.FromHwnd(new WindowInteropHelper(this).Handle);
        if (_hwndSource == null) return;

        _hwndSource.AddHook(WndProc);

        nint hwnd    = _hwndSource.Handle;
        int  exStyle = Win32Api.GetWindowLong(hwnd, WinExStyle.GWL_EXSTYLE);
        // 初始状态：WS_EX_LAYERED + WS_EX_TOOLWINDOW + WS_EX_TRANSPARENT（全穿透）
        exStyle |= WinExStyle.WS_EX_LAYERED | WinExStyle.WS_EX_TOOLWINDOW
                                            | WinExStyle.WS_EX_TRANSPARENT;
        Win32Api.SetWindowLong(hwnd, WinExStyle.GWL_EXSTYLE, exStyle);

        Win32Api.RegisterHotKey(hwnd, HotkeyId, MOD_NONE, VK_F9);

        var ps = PresentationSource.FromVisual(this);
        if (ps?.CompositionTarget != null)
        {
            _dpiScaleX = ps.CompositionTarget.TransformToDevice.M11;
            _dpiScaleY = ps.CompositionTarget.TransformToDevice.M22;
        }
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        _overlayPhysLeft = (int)(Left * _dpiScaleX);
        _overlayPhysTop  = (int)(Top  * _dpiScaleY);

        _ws.OnMessageReceived += HandleServerMessage;
        _ws.OnDisconnected    += msg => Dispatcher.Invoke(() => SetStatus($"● 断开: {msg}", "#FF6B6B"));

        SetStatus("● 正在连接服务器...", "#FFA500");
        await _ws.ConnectAsync();
        SetStatus(_ws.IsConnected ? "● 已连接  按 F9 开始分析" : "● 连接失败  请启动 server/main.py",
                  _ws.IsConnected ? "#4CAF50" : "#FF6B6B");
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        _followTimer.Stop();
        Win32Api.UnregisterHotKey(new WindowInteropHelper(this).Handle, HotkeyId);
        _ = _ws.DisposeAsync();
    }

    // ─── WndProc：仅处理 F9 热键 ──────────────────────────────────────────────
    // 穿透由 WS_EX_TRANSPARENT 在 Win32 层面处理，无需 WM_NCHITTEST 钩子

    private nint WndProc(nint hwnd, int msg, nint wParam, nint lParam, ref bool handled)
    {
        if (msg == WinMsg.WM_HOTKEY && (int)wParam == HotkeyId)
        {
            handled = true;
            _ = TriggerCaptureAsync();
            return nint.Zero;
        }
        return nint.Zero;
    }

    // ─── 穿透切换 ─────────────────────────────────────────────────────────────

    /// <summary>开启穿透：添加 WS_EX_TRANSPARENT，覆盖层完全不拦截鼠标。</summary>
    private void EnableClickThrough()
    {
        nint hwnd    = new WindowInteropHelper(this).Handle;
        int  exStyle = Win32Api.GetWindowLong(hwnd, WinExStyle.GWL_EXSTYLE);
        Win32Api.SetWindowLong(hwnd, WinExStyle.GWL_EXSTYLE,
            exStyle | WinExStyle.WS_EX_TRANSPARENT);
    }

    /// <summary>关闭穿透：移除 WS_EX_TRANSPARENT，覆盖层可接收鼠标（按钮可点击）。</summary>
    private void DisableClickThrough()
    {
        nint hwnd    = new WindowInteropHelper(this).Handle;
        int  exStyle = Win32Api.GetWindowLong(hwnd, WinExStyle.GWL_EXSTYLE);
        Win32Api.SetWindowLong(hwnd, WinExStyle.GWL_EXSTYLE,
            exStyle & ~WinExStyle.WS_EX_TRANSPARENT);
    }

    // ─── 截图 → 发送 ──────────────────────────────────────────────────────────

    private async Task TriggerCaptureAsync()
    {
        SetStatus("● 正在截图分析...", "#FFA500");

        _lastCapCutRect = _tracker.GetCapCutRect();
        if (_lastCapCutRect.Width == 0)
        {
            SetStatus("● 未找到剪映窗口，请先打开剪映", "#FF6B6B");
            return;
        }
        SetStatus($"● [调试] 窗口: ({_lastCapCutRect.Left},{_lastCapCutRect.Top}) {_lastCapCutRect.Width}x{_lastCapCutRect.Height}", "#888888");

        string b64;
        try   { b64 = _capture.CaptureToBase64(_lastCapCutRect); }
        catch (Exception ex) { SetStatus($"● 截图失败: {ex.Message}", "#FF6B6B"); return; }

        SetStatus($"● [调试] base64 长度: {b64.Length}", "#888888");

        await _ws.SendAsync(new
        {
            type = "screenshot",
            data = b64,
            task = _currentTask,
            rect = new
            {
                left   = _lastCapCutRect.Left,
                top    = _lastCapCutRect.Top,
                width  = _lastCapCutRect.Width,
                height = _lastCapCutRect.Height,
            }
        });

        SetStatus("● 等待 AI 响应...", "#FFA500");
    }

    // ─── 处理服务端响应 ───────────────────────────────────────────────────────

    private void HandleServerMessage(Dictionary<string, JsonElement> msg)
    {
        Dispatcher.Invoke(() =>
        {
            string action = msg.TryGetValue("action", out var a) ? a.GetString() ?? "" : "";

            // 所有带坐标的操作（click / highlight / input_text / drag 等）统一绘制黄框
            bool hasBox = msg.TryGetValue("box", out var boxElem)
                          && boxElem.ValueKind == JsonValueKind.Array;

            if (action == "complete")
            {
                string tip = msg.TryGetValue("tooltip", out var t) ? t.GetString() ?? "" : "任务完成！";
                ClearAnnotations();
                ControlPanel.Visibility = Visibility.Visible;
                DisableClickThrough();
                SetStatus($"● ✅ {tip}", "#4CAF50");
            }
            else if (action is "click" or "highlight" or "input_text" or "drag" or "scroll")
            {
                string tip = msg.TryGetValue("tooltip", out var t) ? t.GetString() ?? "" : "";

                if (hasBox)
                {
                    int[] box = [.. boxElem.EnumerateArray().Select(e => e.GetInt32())];
                    _lastBox     = box;
                    _lastTooltip = tip;
                    DrawHighlight(box, tip, _lastCapCutRect);
                }

                // 显示控制面板 + 关闭穿透，使按钮可点击
                ControlPanel.Visibility = Visibility.Visible;
                DisableClickThrough();

                string label = action switch
                {
                    "input_text" => "输入",
                    "drag"       => "拖拽",
                    "scroll"     => "滚动",
                    _            => "已标注"
                };
                SetStatus($"● {label}  {tip}", "#4CAF50");
            }
            else if (action == "none")
            {
                string tip = msg.TryGetValue("tooltip", out var t) ? t.GetString() ?? "" : "";
                SetStatus($"● {tip}", "#FFA500");
            }
            else if (action == "error")
            {
                string errMsg = msg.TryGetValue("message", out var m) ? m.GetString() ?? "" : "未知错误";
                SetStatus($"● 错误: {errMsg}", "#FF6B6B");
            }
            else if (!string.IsNullOrEmpty(action))
            {
                // 未知 action，但有 box 就画框，有 tooltip 就显示
                string tip = msg.TryGetValue("tooltip", out var t) ? t.GetString() ?? "" : action;
                if (hasBox)
                {
                    int[] box = [.. boxElem.EnumerateArray().Select(e => e.GetInt32())];
                    _lastBox     = box;
                    _lastTooltip = tip;
                    DrawHighlight(box, tip, _lastCapCutRect);
                    ControlPanel.Visibility = Visibility.Visible;
                    DisableClickThrough();
                }
                SetStatus($"● {tip}", "#4CAF50");
            }
        });
    }

    // ─── 黄框跟随定时器 ───────────────────────────────────────────────────────

    private void FollowTimer_Tick(object? sender, EventArgs e)
    {
        if (_lastBox == null || _highlightRect?.Visibility != Visibility.Visible) return;

        var rect = _tracker.GetCapCutRect();
        if (rect.Width == 0) return;

        _lastCapCutRect = rect;
        UpdateAnnotationPositions(rect);
    }

    // ─── 绘制黄框 + Tooltip ───────────────────────────────────────────────────

    /// <summary>
    /// 在 Canvas 上创建/更新高亮黄框和 Tooltip 标签。
    /// 元素只创建一次，后续由 UpdateAnnotationPositions 更新位置。
    /// </summary>
    private void DrawHighlight(int[] box, string tooltip, RECT jianyingRect)
    {
        if (box.Length < 4) return;

        (double dipX, double dipY, double dipW, double dipH) = BoxToDip(box, jianyingRect);

        // ── 黄框 ─────────────────────────────────────────────────────────────
        if (_highlightRect == null)
        {
            _highlightRect = new Rectangle
            {
                Stroke           = Brushes.Yellow,
                StrokeThickness  = 3,
                Fill             = new SolidColorBrush(Color.FromArgb(25, 255, 255, 0)),
                IsHitTestVisible = false,
            };
            MainCanvas.Children.Add(_highlightRect);
        }
        _highlightRect.Width      = dipW;
        _highlightRect.Height     = dipH;
        _highlightRect.Visibility = Visibility.Visible;
        Canvas.SetLeft(_highlightRect, dipX);
        Canvas.SetTop(_highlightRect,  dipY);

        // ── Tooltip 标签（黄框顶部正上方）────────────────────────────────────
        if (!string.IsNullOrEmpty(tooltip))
        {
            if (_tooltipLabel == null)
            {
                _tooltipLabel = new Border
                {
                    Background       = new SolidColorBrush(Color.FromArgb(220, 20, 20, 20)),
                    CornerRadius     = new CornerRadius(4),
                    Padding          = new Thickness(8, 4, 8, 4),
                    MaxWidth         = 360,
                    IsHitTestVisible = false,
                    Child            = new TextBlock
                    {
                        Foreground   = Brushes.Yellow,
                        FontSize     = 14,
                        FontFamily   = new FontFamily("Microsoft YaHei UI"),
                        TextWrapping = TextWrapping.Wrap,
                    }
                };
                MainCanvas.Children.Add(_tooltipLabel);
            }
            ((TextBlock)_tooltipLabel.Child).Text = tooltip;
            _tooltipLabel.Visibility = Visibility.Visible;
            _tooltipLabel.Measure(new Size(360, double.PositiveInfinity));
            double labelH = _tooltipLabel.DesiredSize.Height > 0 ? _tooltipLabel.DesiredSize.Height : 28;
            Canvas.SetLeft(_tooltipLabel, dipX);
            Canvas.SetTop(_tooltipLabel,  Math.Max(0, dipY - labelH - 6));
        }
        else if (_tooltipLabel != null)
        {
            _tooltipLabel.Visibility = Visibility.Collapsed;
        }
    }

    /// <summary>仅更新已有标注元素的 Canvas 坐标（Timer 每 100ms 调用）。</summary>
    private void UpdateAnnotationPositions(RECT jianyingRect)
    {
        if (_lastBox == null || _highlightRect == null) return;

        (double dipX, double dipY, double dipW, double dipH) = BoxToDip(_lastBox, jianyingRect);

        _highlightRect.Width  = dipW;
        _highlightRect.Height = dipH;
        Canvas.SetLeft(_highlightRect, dipX);
        Canvas.SetTop(_highlightRect,  dipY);

        if (_tooltipLabel?.Visibility == Visibility.Visible)
        {
            _tooltipLabel.Measure(new Size(360, double.PositiveInfinity));
            double labelH = _tooltipLabel.DesiredSize.Height > 0 ? _tooltipLabel.DesiredSize.Height : 28;
            Canvas.SetLeft(_tooltipLabel, dipX);
            Canvas.SetTop(_tooltipLabel,  Math.Max(0, dipY - labelH - 6));
        }
    }

    /// <summary>box 物理像素（相对剪映截图左上角）→ WPF DIP（相对覆盖层左上角）。</summary>
    private (double dipX, double dipY, double dipW, double dipH) BoxToDip(int[] box, RECT jianyingRect)
    {
        const double pad = 12.0;
        double dipX = (jianyingRect.Left + box[0] - _overlayPhysLeft) / _dpiScaleX - pad;
        double dipY = (jianyingRect.Top  + box[1] - _overlayPhysTop)  / _dpiScaleY - pad;
        double dipW = box[2] / _dpiScaleX + pad * 2;
        double dipH = box[3] / _dpiScaleY + pad * 2;
        return (dipX, dipY, dipW, dipH);
    }

    private void ClearAnnotations()
    {
        if (_highlightRect != null) _highlightRect.Visibility = Visibility.Collapsed;
        if (_tooltipLabel  != null) _tooltipLabel.Visibility  = Visibility.Collapsed;
        _lastBox     = null;
        _lastTooltip = null;
    }

    // ─── 按钮事件 ─────────────────────────────────────────────────────────────

    private void BtnNext_Click(object sender, RoutedEventArgs e)
    {
        // 隐藏控制面板 + 恢复全穿透，然后重新截图分析
        ControlPanel.Visibility = Visibility.Collapsed;
        EnableClickThrough();
        ClearAnnotations();
        _ = TriggerCaptureAsync();
    }

    private void BtnDone_Click(object sender, RoutedEventArgs e)
    {
        // 隐藏控制面板 + 恢复全穿透，回到待机状态
        ControlPanel.Visibility = Visibility.Collapsed;
        EnableClickThrough();
        ClearAnnotations();
        SetStatus("● 已完成  按 F9 开始新的分析", "#4CAF50");
    }

    // ─── 辅助 ─────────────────────────────────────────────────────────────────

    private void SetStatus(string text, string hexColor)
    {
        StatusText.Text       = text;
        StatusText.Foreground = new SolidColorBrush(
            (Color)ColorConverter.ConvertFromString(hexColor));
    }
}
