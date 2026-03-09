# 配置管理说明

## 📋 概述

系统配置已统一到 `config.py` 模块，支持通过环境变量（`.env` 文件）进行配置。

## 🔧 配置文件结构

```
server/
├── config.py          # 配置管理模块（统一入口）
├── .env               # 实际配置文件（不提交到 Git）
└── .env.example       # 配置模板（可提交到 Git）
```

## ⚙️ 配置项说明

### 1. 服务器配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| 服务器地址 | `SERVER_HOST` | `0.0.0.0` | 监听地址（0.0.0.0 表示所有网卡） |
| 服务器端口 | `SERVER_PORT` | `8000` | WebSocket 服务端口 |
| 日志级别 | `LOG_LEVEL` | `info` | 可选: debug, info, warning, error |

### 2. LLM 配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| API Key | `OPENAI_API_KEY` | **必需** | OpenAI API 密钥（或兼容 API） |
| API 端点 | `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 基础 URL |
| 模型名称 | `LLM_MODEL` | `gpt-4o` | 使用的模型名称 |
| Temperature | `LLM_TEMPERATURE` | `0.1` | 生成随机性（0-2） |
| Max Tokens | `LLM_MAX_TOKENS` | `500` | 最大返回 Token 数 |

### 3. 用户配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| 默认用户目标 | `DEFAULT_USER_GOAL` | `加一个老电视特效` | 默认的操作目标 |

### 4. 开发模式配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| 降级模式 | `ENABLE_FALLBACK` | `true` | LLM 失败时使用硬编码响应 |
| 详细日志 | `VERBOSE_LOGGING` | `true` | 是否输出详细日志 |

### 5. 性能配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| 最大连接数 | `MAX_CONNECTIONS` | `10` | 最大并发 WebSocket 连接 |
| 图片大小限制 | `MAX_IMAGE_SIZE` | `10485760` | 截图最大字节数（10MB） |

## 🚀 使用方法

### 1. 初次配置

```bash
# 进入服务端目录
cd server

# 复制配置模板
cp .env.example .env

# 编辑配置文件
notepad .env  # Windows
# 或
nano .env     # Linux/Mac
```

### 2. 填写配置

在 `.env` 文件中修改：

```ini
# 必需配置
OPENAI_API_KEY=sk-your-actual-api-key-here

# 可选配置（根据需要修改）
SERVER_PORT=8000
LLM_MODEL=gpt-4o
DEFAULT_USER_GOAL=加一个老电视特效
```

### 3. 验证配置

```bash
# 验证配置是否正确
python config.py
```

输出示例：
```
📋 当前系统配置
============================================================
🌐 服务器地址: 0.0.0.0:8000
🔗 WebSocket 端点: ws://0.0.0.0:8000/ws
🤖 LLM 模型: gpt-4o
🔑 API Key: ✅ 已设置
🌍 API Base URL: https://api.openai.com/v1
...
✅ 配置验证通过
```

## 🔌 在代码中使用配置

```python
from config import config

# 访问配置
port = config.SERVER_PORT
api_key = config.OPENAI_API_KEY
model = config.LLM_MODEL

# 配置验证
if config.validate():
    print("配置正确")

# 打印配置信息
config.print_config()
```

## 🔒 安全注意事项

1. **`.env` 文件包含敏感信息**，已自动添加到 `.gitignore`，不会被提交到 Git
2. **不要在代码中硬编码** API Key 或其他敏感信息
3. **生产环境**建议使用环境变量或密钥管理服务

## 📝 自定义配置

如需添加新的配置项：

1. 在 `config.py` 的 `Config` 类中添加属性
2. 在 `.env.example` 中添加说明
3. 在本文档中更新配置表

示例：

```python
# config.py
class Config:
    # 新增配置
    CUSTOM_OPTION: str = os.getenv("CUSTOM_OPTION", "default_value")
```

```ini
# .env.example
# 自定义配置说明
CUSTOM_OPTION=your_value
```

## 🆘 常见问题

### Q: 修改配置后没有生效？
A: 需要重启服务：停止 Python 进程，重新运行 `python main.py`

### Q: 如何使用第三方 API（如国内中转）？
A: 修改 `.env` 中的 `OPENAI_BASE_URL`：
```ini
OPENAI_BASE_URL=https://your-proxy.com/v1
```

### Q: 如何禁用降级模式？
A: 修改 `.env`：
```ini
ENABLE_FALLBACK=false
```

### Q: 如何更改服务端口？
A: 修改 `.env`：
```ini
SERVER_PORT=9000
```
同时需要修改客户端连接地址（C# 代码中的 WebSocket URL）

---

**最后更新**: 2026-02-27
