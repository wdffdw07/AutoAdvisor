# AutoDirector Copilot - 剪映智导

视频剪辑领域的 "GitHub Copilot"，通过多模态大模型实现"说到哪，指到哪"的保姆级剪辑导航。

## 🎯 项目状态

- ✅ **Phase 1**：透明穿透窗口 + 窗口追踪
- ✅ **Phase 2**：端云 WebSocket 通信
- ✅ **Phase 3**：大模型动态推理（当前阶段）

## 🏗️ 技术架构

- **客户端**：C# .NET WPF（轻量级，<30MB）
- **服务端**：Python FastAPI + WebSocket
- **AI 大脑**：GLM-4V / GPT-4o（多模态视觉理解）

## 🚀 快速开始

### 1. 配置 API（推荐使用 GLM-4V）

详细步骤见：[GLM-4V 配置指南](server/GLM_SETUP.md)

**快速配置**：
```powershell
# 1. 访问 https://open.bigmodel.cn/ 获取 API Key
# 2. 编辑 server/.env 文件
notepad server\.env

# 3. 填入 API Key
GLM_API_KEY=粘贴你的API_Key
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_MODEL=glm-4v
```

### 2. 安装依赖

```powershell
# Python 服务端
cd server
pip install -r requirements.txt
# 或使用 uv: uv pip install -r requirements.txt

# C# 客户端（已编译无需额外安装）
cd client
dotnet build
```

### 3. 启动服务

**终端 1 - Python 服务端**：
```powershell
cd D:\software\AutoDirectorCopilot\server
python main.py
# 或: .\.venv\Scripts\python.exe main.py
```

**终端 2 - C# 客户端**：
```powershell
cd D:\software\AutoDirectorCopilot\client
dotnet run
```

### 4. 测试

1. 打开 **剪映专业版**
2. 按 **F9** 键（全局热键）触发AI分析
3. 等待 2-5 秒，屏幕上会显示黄色高亮框和提示文字
4. 按照提示完成操作（如点击指定按钮）
5. 点击右侧绿色 **"下一步"** 按钮继续下一步
6. 重复步骤 4-5 直到任务完成

**交互模式**：手动步进控制
- 黄色高亮框指示目标位置
- 绿色"下一步"按钮控制流程进度
- 用户完全掌控操作节奏
- 避免过快的 API 请求

## 📁 项目结构

```
AutoDirectorCopilot/
├── client/                 # C# WPF 客户端
│   ├── MainWindow.xaml     # 透明穿透窗口
│   ├── MainWindow.xaml.cs  # 主逻辑（热键、渲染）
│   ├── WindowTracker.cs    # 窗口追踪
│   ├── ScreenCapture.cs    # 截图模块
│   └── WebSocketClient.cs  # WebSocket 通信
├── server/                 # Python 服务端
│   ├── main.py            # FastAPI 服务入口
│   ├── llm_agent.py       # LLM Agent 核心模块
│   ├── schema.json        # UI 拓扑地图
│   ├── .env               # 环境变量配置
│   ├── requirements.txt   # Python 依赖
│   └── GLM_SETUP.md       # GLM 配置指南
└── architecture.md        # 系统设计文档
```

## 🧪 Phase 3 功能

当前 Phase 3 已实现：
- ✅ UI 拓扑地图（schema.json）
- ✅ LLM Agent 动态推理引擎
- ✅ 支持 GLM-4V / GPT-4o
- ✅ 多模态图像理解
- ✅ JSON 指令生成
- ✅ 降级模式（LLM 失败时）

**工作流程**：
```
用户按 F9 → 截图剪映窗口 → 发送到服务器
    ↓
LLM Agent 接收
    ├─ 加载 UI 拓扑地图
    ├─ 构建 System Prompt
    └─ 调用多模态大模型分析截图
    ↓
返回操作指令：{"box": [x,y,w,h], "tooltip": "..."}
    ↓
客户端渲染黄色高亮框 + 提示文字
```

## 💡 使用场景示例

**用户目标**：给视频加一个老电视特效

1. **第一步**：LLM 识别当前界面，高亮显示【特效】菜单按钮
2. **第二步**：用户点击后，LLM 识别到特效面板已打开，高亮显示搜索框
3. **第三步**：用户搜索"老电视"，LLM 识别搜索结果，高亮第一个特效
4. **第四步**：提示用户将特效拖拽到时间轴

## 🔧 故障排查

### 客户端无法连接服务器
```
⚠️ 无法连接到云端服务
```
**解决**：确保 Python 服务已启动，端口 8000 未被占用

### 未找到剪映窗口
```
⚠️ 未找到剪映窗口
```
**解决**：确保剪映专业版已打开，窗口标题包含"剪映"

### LLM 调用失败
```
❌ LLM 分析失败
```
**解决**：
1. 检查 `.env` 中的 API Key 是否正确
2. 检查网络连接
3. 查看余额是否充足
4. 降级模式会自动启用

## 📊 性能指标

- **客户端内存占用**：< 30MB
- **窗口追踪频率**：10 FPS（100ms/次）
- **LLM 响应时间**：2-5 秒（取决于网络）
- **坐标精度**：像素级

## 🎯 下一步开发（未来）

- [ ] SoM 标记系统（给 UI 元素打数字标签）
- [ ] 多轮对话状态管理
- [ ] 拖拽动作自动化
- [ ] 语音输入支持
- [ ] 更多剪映功能覆盖

## 📚 文档

- [系统架构设计](architecture.md)
- [Phase 2 测试指南](PHASE2_TEST.md)
- [GLM-4V 配置指南](server/GLM_SETUP.md)

## 📄 许可证

MIT License

---

**当前版本**：Phase 3 MVP  
**最后更新**：2026-02-27
