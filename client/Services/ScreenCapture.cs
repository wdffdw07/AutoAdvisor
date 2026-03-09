// Services/ScreenCapture.cs
// 职责：接收物理像素 RECT，截取对应屏幕区域，以 Base64 JPEG 返回。
//       不依赖任何 UI 层，可独立单元测试。
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using CopilotClient.Core;

namespace CopilotClient.Services;

public class ScreenCapture
{
    // JPEG 压缩质量（80 在质量和体积之间取得平衡）
    private const int JpegQuality = 80;

    /// <summary>
    /// 使用 GDI+ 截取指定物理像素矩形的屏幕内容。
    /// </summary>
    /// <param name="rect">来自 GetWindowRect 的物理像素矩形。</param>
    /// <returns>JPEG 图片的 Base64 字符串（不含 data URI 前缀）。</returns>
    /// <exception cref="InvalidOperationException">矩形尺寸无效时抛出。</exception>
    public string CaptureToBase64(RECT rect)
    {
        int w = rect.Width;
        int h = rect.Height;

        if (w <= 0 || h <= 0)
            throw new InvalidOperationException($"无效的截图区域：{w}x{h}，请确认剪映已打开。");

        using var bmp = new Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using var g   = Graphics.FromImage(bmp);

        // Graphics.CopyFromScreen 使用物理像素坐标，与 GetWindowRect 完全对应
        g.CopyFromScreen(rect.Left, rect.Top, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);

        // 编码为 JPEG 并转 Base64
        using var ms = new MemoryStream();
        var encoder  = GetJpegEncoder();
        var encParams = new EncoderParameters(1);
        encParams.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, (long)JpegQuality);

        bmp.Save(ms, encoder, encParams);
        return Convert.ToBase64String(ms.ToArray());
    }

    // ─── 私有辅助 ─────────────────────────────────────────────────────────────

    private static ImageCodecInfo GetJpegEncoder()
    {
        foreach (var codec in ImageCodecInfo.GetImageEncoders())
            if (codec.MimeType == "image/jpeg") return codec;

        throw new InvalidOperationException("系统不支持 JPEG 编码器");
    }
}
