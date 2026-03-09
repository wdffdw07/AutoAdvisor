# AutoDirector Copilot — Electron 客户端壳（Step2 Mock）

**状态**：Step2 ✅ — Mock 数据跑通完整引导流程

## 目录结构

```
client-electron/
├── electron/
│   ├── main.js       # Electron 主进程（窗口管理、IPC 路由）
│   ├── preload.js    # contextBridge（Renderer ↔ Main 安全通信）
│   └── mock.js       # Mock 会话编排（3 步 Photoshop 高斯模糊场景）
├── renderer/
│   ├── capsule.html  # 胶囊 UI 入口
│   ├── capsule.js    # 胶囊 UI 渲染器逻辑
│   ├── overlay.html  # 透明叠加层入口
│   ├── overlay.js    # 叠加层渲染器逻辑
│   └── styles.css    # 胶囊 UI 样式（深色玻璃态）
├── package.json
└── .gitignore
```

## 前置要求

安装 **Node.js 18+**（LTS）：https://nodejs.org/

验证：
```powershell
node -v   # v18.x 或以上
npm -v
```

## 安装与运行

```powershell
cd D:\software\AutoDirectorCopilot\project\client-electron
npm install
npm start
```

## 验收步骤（Step2）

1. 运行后出现**深色玻璃态胶囊**悬浮在屏幕左侧
2. 输入框填入目标（如「给图片加高斯模糊」）或直接点击**开始引导**
3. 胶囊显示 Step 1/3，描述「点击顶部【滤镜】菜单」
4. **全屏透明叠加层**在模拟位置渲染紫色呼吸灯高亮框
5. 点击**下一步** → 进入 Step 2/3（点击【模糊→高斯模糊】），高亮框移位
6. 再点**下一步** → 进入 Step 3/3（连续动作），显示「等待操作」提示，高亮隐藏
7. 点击**下一步** → 胶囊显示**完成**卡片，高亮消失
8. F9 快捷键可将焦点回到输入框（空闲状态）

## Mock 数据描述

仿真场景：Photoshop 高斯模糊（符合验收样本 B）

| 步骤 | 动作类型 | 描述                       | 推进方式   |
|------|----------|----------------------------|------------|
| 1/3  | click    | 点击顶部【滤镜】菜单         | 自动（下一步） |
| 2/3  | click    | 悬停【模糊】→ 点击【高斯模糊】| 自动（下一步） |
| 3/3  | drag     | 拖动【半径】滑块             | 手动（等待用户） |

仿真窗口坐标：`window_box = [100, 50, 1400, 900]`（主屏，dpi_scale=1.0）

## 已知限制（Step2 范围内）

- 无真实 AI：全部使用 Mock 数据
- 无真实 WS 连接：Step3 引入
- Context Sniffer（窗口识别/截图）：Step4 引入
- 高亮坐标为硬编码仿真值，不跟随真实应用窗口

## 兼容性结论

- **旧基线 WPF（`project/client/`）未改动** ✅
- **服务端（`project/server/`）未改动** ✅
- 本目录完全独立，不影响任何现有运行路径
