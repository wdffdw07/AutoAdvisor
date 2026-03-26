"""
AutoDirector Copilot Server
"""
import json
import os
from datetime import datetime

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from api.ws_router import build_session_error, handle_client_payload
from llm_agent import get_agent
from services.llm_service import LLMSessionService


def _ascii_safe(value: object) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _log(message: str) -> None:
    print(_ascii_safe(message))


load_dotenv()

app = FastAPI(title="AutoDirector Copilot Server")
active_connections: list[WebSocket] = []


@app.get("/")
async def root():
    return {
        "service": "AutoDirector Copilot Server",
        "status": "running",
        "version": "1.0.0-MVP",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
        },
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(active_connections),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    client_id = id(websocket)

    _log(f"[INFO] Client connected [id={client_id}]")
    _log(f"[INFO] Active connections: {len(active_connections)}")

    try:
        service = LLMSessionService(get_agent)
        _log("[INFO] LLM agent ready")
    except Exception as error:
        _log(f"[ERROR] LLM agent initialization failed: {error}")
        service = None

    try:
        session_state = None
        while True:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")
                _log(f"\n[INFO] Received message type: {msg_type}")

                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    continue

                if service is None:
                    responses = [
                        build_session_error(
                            "E_INTERNAL",
                            "LLM service unavailable",
                            recoverable=False,
                            trace_id=data.get("trace_id", "server-trace"),
                            session_id=data.get("session_id"),
                        )
                    ]
                else:
                    try:
                        session_state, responses = await handle_client_payload(data, session_state, service)
                    except Exception as routing_error:
                        _log(f"  [ERROR] Session routing failed: {routing_error}")
                        responses = [
                            build_session_error(
                                "E_INTERNAL",
                                str(routing_error),
                                recoverable=False,
                                trace_id=data.get("trace_id", "server-trace"),
                                session_id=data.get("session_id") or (session_state.session_id if session_state else None),
                            )
                        ]

                for response in responses:
                    await websocket.send_text(json.dumps(response))
                    _log(f"  [INFO] Sent response: {response}")

            except json.JSONDecodeError:
                _log("  [ERROR] JSON parse failed")
                await websocket.send_text(
                    json.dumps(
                        build_session_error(
                            "E_BAD_REQUEST",
                            "Invalid JSON format",
                            recoverable=False,
                        )
                    )
                )

    except WebSocketDisconnect:
        if websocket in active_connections:
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
        log_level="info",
    )
