"""
AutoDirector Copilot - 云端服务
Phase 3: 集成多模态大模型，实现动态 UI 理解和操作指引
"""
import json
import os
from datetime import datetime

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from llm_agent import get_agent


def _ascii_safe(value: object) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _log(message: str) -> None:
    print(_ascii_safe(message))


load_dotenv()

app = FastAPI(title="AutoDirector Copilot Server")
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

    _log(f"[INFO] Client connected [id={client_id}]")
    _log(f"[INFO] Active connections: {len(active_connections)}")

    try:
        agent = get_agent()
        _log("[INFO] LLM agent ready")
    except Exception as error:
        _log(f"[ERROR] LLM agent initialization failed: {error}")
        _log("[WARN] Falling back to hardcoded responses")
        agent = None

    try:
        while True:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")

                _log(f"\n[INFO] Received message type: {msg_type}")

                if msg_type == "screenshot":
                    image_data = data.get("data", "")
                    window_rect = data.get("windowRect", {})

                    _log(f"  [INFO] Screenshot size: {len(image_data)} chars (Base64)")
                    _log(f"  [INFO] Window rect: {window_rect}")

                    if agent is not None:
                        try:
                            response = await agent.analyze_screenshot(
                                base64_image=image_data,
                                user_goal="加一个老电视特效"
                            )
                        except Exception as llm_error:
                            _log(f"  [ERROR] LLM analysis failed: {llm_error}")
                            response = {
                                "action": "click",
                                "box": [200, 50, 100, 40],
                                "tooltip": "AI 暂时不可用，这是默认位置"
                            }
                    else:
                        response = {
                            "action": "click",
                            "box": [200, 50, 100, 40],
                            "tooltip": "点击特效（降级模式）"
                        }

                    await websocket.send_text(json.dumps(response))
                    _log(f"  [INFO] Sent response: {response}")

                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                else:
                    _log(f"  [WARN] Unknown message type: {msg_type}")

            except json.JSONDecodeError:
                _log("  [ERROR] JSON parse failed")
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        _log(f"\n[INFO] Client disconnected [id={client_id}]")
        _log(f"[INFO] Active connections: {len(active_connections)}")

    except Exception as error:
        _log(f"\n[ERROR] WebSocket failure: {error}")
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    print("=" * 60)
    _log("[INFO] AutoDirector Copilot server starting (Phase 3)")
    print("=" * 60)
    _log("[INFO] WebSocket endpoint: ws://127.0.0.1:8000/ws")
    _log("[INFO] HTTP endpoint: http://127.0.0.1:8000")
    _log("[INFO] Health endpoint: http://127.0.0.1:8000/health")
    print("=" * 60)

    has_glm = bool(os.getenv("GLM_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if has_glm:
        _log("[INFO] GLM API key configured")
        _log(f"[INFO] Model: {os.getenv('LLM_MODEL', 'glm-4v')}")
    elif has_openai:
        _log("[INFO] OpenAI API key configured")
        _log(f"[INFO] Model: {os.getenv('LLM_MODEL', 'gpt-4o')}")
    else:
        _log("[WARN] No API key configured")
        _log("[WARN] Configure GLM_API_KEY or OPENAI_API_KEY in .env")
        _log("[WARN] Hardcoded fallback mode will be used")

    print("=" * 60)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
