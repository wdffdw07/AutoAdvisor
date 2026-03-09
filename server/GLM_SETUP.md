# GLM-4V 配置指南

## 🚀 快速开始（使用智谱 AI GLM-4V）

GLM-4V 是智谱 AI 提供的多模态大模型，支持图像理解，**国内可直接访问，无需翻墙**。

### 为什么选择 GLM-4V？
- ✅ **国内可用**：无需国际网络，访问速度快
- ✅ **价格便宜**：约 0.005 元/次调用，比 GPT-4o 便宜 10+ 倍
- ✅ **性能优秀**：多模态理解能力强，适合 UI 识别任务
- ✅ **易于接入**：兼容 OpenAI SDK，零代码改动

---

## 📝 配置步骤

### 1. 注册智谱 AI 账号

访问：https://open.bigmodel.cn/

- 点击右上角【注册/登录】
- 支持手机号或微信登录
- 新用户赠送一定额度的免费试用

### 2. 获取 API Key

登录后访问：https://open.bigmodel.cn/usercenter/apikeys

- 点击【创建新的 API Key】
- 复制生成的 API Key（格式类似：`abc123.xyz456789...`）
- ⚠️ **API Key 只显示一次，请务必保存好！**

### 3. 配置项目

打开 `server/.env` 文件，填入你的 API Key：

```ini
GLM_API_KEY=粘贴你的API_Key
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_MODEL=glm-4v
```

**示例**：
```ini
GLM_API_KEY=abc123def456.xyz789012345678901234567890
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_MODEL=glm-4v
```

### 4. 安装依赖

```powershell
cd server
pip install -r requirements.txt
# 或使用 uv: uv pip install -r requirements.txt
```

### 5. 启动服务

```powershell
cd D:\software\AutoDirectorCopilot\server
python main.py
# 或指定 Python 路径: .\.venv\Scripts\python.exe main.py
```

看到以下输出表示成功：
```
============================================================
🚀 AutoDirector Copilot 云端服务启动中... (Phase 3)
============================================================
📡 WebSocket 端点: ws://127.0.0.1:8000/ws
🌐 HTTP 端点: http://127.0.0.1:8000
💊 健康检查: http://127.0.0.1:8000/health
============================================================
✅ GLM API 已配置
   模型: glm-4v
============================================================
```

---

## 🧪 测试

1. **启动客户端**
   ```powershell
   cd D:\software\AutoDirectorCopilot\client
   dotnet run
   ```

2. **打开剪映专业版**

3. **按 F9 触发截图**
   - 客户端会截取剪映窗口
   - 发送到服务器
   - GLM-4V 分析截图（约 2-5 秒）
   - 屏幕显示高亮框

---

## 💰 价格参考（2026 年 2 月）

| 模型 | 图像理解能力 | 价格/次 | 适用场景 |
|------|------------|---------|---------|
| GLM-4V | ⭐⭐⭐⭐ | ¥0.005 | 推荐，性价比高 |
| GPT-4o | ⭐⭐⭐⭐⭐ | ¥0.08 | 预算充足 |
| GPT-4V | ⭐⭐⭐⭐ | ¥0.06 | - |

---

## 🔧 故障排查

### 问题 1：API Key 无效
```
❌ 未设置 API Key，请在 .env 中配置 GLM_API_KEY
```
**解决**：
- 确认 `.env` 文件在 `server/` 目录下
- 确认 API Key 已正确粘贴（无多余空格）
- 检查 API Key 是否已被删除或过期

### 问题 2：连接超时
```
❌ LLM 调用失败: Connection timeout
```
**解决**：
- 检查网络连接
- 确认防火墙未拦截 Python 进程

### 问题 3：余额不足
```
❌ LLM 调用失败: Insufficient balance
```
**解决**：
- 访问智谱 AI 控制台充值
- 或使用降级模式（Phase 2 硬编码响应）

---

## 🔄 切换回 OpenAI（可选）

如果你有 OpenAI API Key，可以修改 `.env`：

```ini
# 注释掉 GLM 配置
# GLM_API_KEY=...
# GLM_BASE_URL=...

# 启用 OpenAI 配置
OPENAI_API_KEY=sk-your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

---

## 📚 相关文档

- 智谱 AI 官方文档：https://open.bigmodel.cn/dev/api
- OpenAI SDK 文档：https://platform.openai.com/docs/api-reference

---

**配置完成后，即可体验 Phase 3 的大模型驱动功能！** 🎉
