// Services/WsClientService.cs
// 职责：封装 .NET 原生 ClientWebSocket，对外暴露 Connect / Send / Disconnect
//       和 OnMessageReceived 事件。不含任何 UI 或 AI 逻辑。
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace CopilotClient.Services;

public class WsClientService : IAsyncDisposable
{
    private const string ServerUri  = "ws://127.0.0.1:8000/ws";
    private const int    BufferSize = 64 * 1024; // 64 KB 接收缓冲

    private ClientWebSocket? _ws;
    private CancellationTokenSource? _cts;

    // ─── 公开事件 ─────────────────────────────────────────────────────────────

    /// <summary>收到服务端 JSON 响应时触发。参数为反序列化后的字典。</summary>
    public event Action<Dictionary<string, JsonElement>>? OnMessageReceived;

    /// <summary>连接断开或出现异常时触发。参数为错误描述。</summary>
    public event Action<string>? OnDisconnected;

    // ─── 连接状态 ─────────────────────────────────────────────────────────────

    public bool IsConnected =>
        _ws?.State == WebSocketState.Open;

    // ─── 公开方法 ─────────────────────────────────────────────────────────────

    /// <summary>
    /// 建立 WebSocket 连接并在后台启动接收循环。
    /// 调用方无需 await，连接失败时 OnDisconnected 会被触发。
    /// </summary>
    public async Task ConnectAsync()
    {
        // 若已连接则先清理旧连接
        await DisposeInternalAsync();

        _cts = new CancellationTokenSource();
        _ws  = new ClientWebSocket();

        try
        {
            await _ws.ConnectAsync(new Uri(ServerUri), _cts.Token);
            // 后台持续接收消息，不阻塞调用方
            _ = Task.Run(ReceiveLoopAsync, _cts.Token);
        }
        catch (Exception ex)
        {
            OnDisconnected?.Invoke($"连接失败: {ex.Message}");
        }
    }

    /// <summary>
    /// 发送 JSON 消息到服务端。
    /// </summary>
    /// <param name="payload">将被序列化为 JSON 的对象。</param>
    public async Task SendAsync(object payload)
    {
        if (!IsConnected)
        {
            OnDisconnected?.Invoke("WebSocket 未连接，尝试重连...");
            await ConnectAsync();
            if (!IsConnected) return;
        }

        string json  = JsonSerializer.Serialize(payload);
        byte[] bytes = Encoding.UTF8.GetBytes(json);
        await _ws!.SendAsync(bytes, WebSocketMessageType.Text, true, _cts!.Token);
    }

    // ─── 后台接收循环 ─────────────────────────────────────────────────────────

    private async Task ReceiveLoopAsync()
    {
        var buffer = new byte[BufferSize];

        try
        {
            while (_ws!.State == WebSocketState.Open && !_cts!.IsCancellationRequested)
            {
                using var ms = new System.IO.MemoryStream();
                WebSocketReceiveResult result;

                // 分帧读取（大消息可能跨多帧）
                do
                {
                    result = await _ws.ReceiveAsync(buffer, _cts.Token);
                    ms.Write(buffer, 0, result.Count);
                } while (!result.EndOfMessage);

                if (result.MessageType == WebSocketMessageType.Close)
                {
                    OnDisconnected?.Invoke("服务端主动关闭连接");
                    break;
                }

                string rawJson = Encoding.UTF8.GetString(ms.ToArray());
                ParseAndNotify(rawJson);
            }
        }
        catch (OperationCanceledException)
        {
            // 正常取消，静默退出
        }
        catch (Exception ex)
        {
            OnDisconnected?.Invoke($"接收异常: {ex.Message}");
        }
    }

    private void ParseAndNotify(string rawJson)
    {
        try
        {
            var dict = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(rawJson);
            if (dict != null)
                OnMessageReceived?.Invoke(dict);
        }
        catch (JsonException ex)
        {
            OnDisconnected?.Invoke($"响应解析失败: {ex.Message}");
        }
    }

    // ─── 清理 ─────────────────────────────────────────────────────────────────

    private async Task DisposeInternalAsync()
    {
        if (_cts != null) { _cts.Cancel(); _cts.Dispose(); _cts = null; }
        if (_ws  != null)
        {
            try
            {
                if (_ws.State == WebSocketState.Open)
                    await _ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "客户端关闭", CancellationToken.None);
            }
            catch { /* 忽略关闭时的异常 */ }
            _ws.Dispose();
            _ws = null;
        }
    }

    public async ValueTask DisposeAsync() => await DisposeInternalAsync();
}
