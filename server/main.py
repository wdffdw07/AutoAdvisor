"""
AutoDirector Copilot - 云端服务
Phase 3: 集成多模态大模型，实现动态 UI 理解和操作指引
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import uvicorn
from datetime import datetime
from dotenv import load_dotenv
import os

# 导入 LLM Agent
from llm_agent import get_agent

# 加载环境变量
load_dotenv()

app = FastAPI(title="AutoDirector Copilot Server")

# 存储活跃的WebSocket连接
active_connections: list[WebSocket] = []


@app.get("/")
async def root():
    """根路径 - 服务健康检查"""
    return {
        "service": "AutoDirector Copilot Server",
        "status": "running",
        "version": "1.0.0-MVP",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(active_connections)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点 - 接收客户端截图并返回操作指令
    
    接收格式:
    {
        "type": "screenshot",
        "data": "base64_encoded_image...",
        "windowRect": {"left": 100, "top": 200, "width": 1920, "height": 1080}
    }
    
    返回格式 (Phase 3 - 真实 LLM 响应):
    {
        "action": "highlight",
        "box": [200, 50, 100, 40],  # [x, y, width, height] 相对剪映窗口
        "tooltip": "点击特效"
    }
    """
    await websocket.accept()
    active_connections.append(websocket)
    client_id = id(websocket)
    
    print(f"✅ 客户端已连接 [ID: {client_id}]")
    print(f"📊 当前活跃连接数: {len(active_connections)}")
    
    # 初始化 LLM Agent（如果尚未初始化）
    try:
        agent = get_agent()
        print(f"✅ LLM Agent 已就绪")
    except Exception as e:
        print(f"❌ LLM Agent 初始化失败: {e}")
        print(f"⚠️  将使用降级模式（硬编码响应）")
        agent = None
    
    try:
        while True:
            # 接收客户端消息
            message = await websocket.receive_text()
            
            try:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")
                
                print(f"\n📥 收到消息类型: {msg_type}")
                
                if msg_type == "screenshot":
                    # 获取截图信息
                    image_data = data.get("data", "")
                    window_rect = data.get("windowRect", {})
                    
                    print(f"  📸 截图大小: {len(image_data)} 字符 (Base64)")
                    print(f"  🪟 窗口位置: {window_rect}")
                    
                    # ============================================
                    # Phase 3: 使用真实 LLM 进行动态推理
                    # ============================================
                    if agent is not None:
                        try:
                            # 调用 LLM Agent 分析截图
                            response = await agent.analyze_screenshot(
                                base64_image=image_data,
                                user_goal="加一个老电视特效"  # 未来可从客户端传入
                            )
                        except Exception as llm_error:
                            print(f"  ❌ LLM 分析失败: {llm_error}")
                            # 降级到硬编码响应
                            response = {
                                "action": "click",
                                "box": [200, 50, 100, 40],
                                "tooltip": "AI 暂时不可用，这是默认位置"
                            }
                    else:
                        # 降级模式：硬编码响应
                        response = {
                            "action": "click",
                            "box": [200, 50, 100, 40],
                            "tooltip": "点击特效（降级模式）"
                        }
                    
                    # 发送响应（直接发送，不再覆盖 action）
                    await websocket.send_text(json.dumps(response))
                    print(f"  📤 已发送指令: {response}")
                
                elif msg_type == "ping":
                    # 心跳包
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
                else:
                    print(f"  ⚠️  未知消息类型: {msg_type}")
                    
            except json.JSONDecodeError:
                print(f"  ❌ JSON 解析失败")
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"\n❌ 客户端断开连接 [ID: {client_id}]")
        print(f"📊 当前活跃连接数: {len(active_connections)}")
    
    except Exception as e:
        print(f"\n💥 WebSocket 错误: {str(e)}")
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 AutoDirector Copilot 云端服务启动中... (Phase 3)")
    print("=" * 60)
    print(f"📡 WebSocket 端点: ws://127.0.0.1:8000/ws")
    print(f"🌐 HTTP 端点: http://127.0.0.1:8000")
    print(f"💊 健康检查: http://127.0.0.1:8000/health")
    print("=" * 60)
    
    # 检查环境变量
    has_glm = bool(os.getenv("GLM_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    
    if has_glm:
        print("✅ GLM API 已配置")
        print(f"   模型: {os.getenv('LLM_MODEL', 'glm-4v')}")
    elif has_openai:
        print("✅ OpenAI API 已配置")
        print(f"   模型: {os.getenv('LLM_MODEL', 'gpt-4o')}")
    else:
        print("⚠️  警告: 未设置 API Key")
        print("   请在 .env 文件中配置 GLM_API_KEY 或 OPENAI_API_KEY")
        print("   或使用降级模式（硬编码响应）")
    
    print("=" * 60)
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
