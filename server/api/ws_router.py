from __future__ import annotations


REQUIRED_V1_COMMON_FIELDS = ("trace_id", "session_id")
REQUIRED_V1_START_FIELDS = ("goal", "context", "image_base64")
REQUIRED_CONTEXT_FIELDS = ("process_name", "window_title", "dpi_scale", "window_box")


def build_session_error(code: str, message: str, recoverable: bool) -> dict:
    return {
        "protocol_version": "v1",
        "event": "session.error",
        "code": code,
        "message": message,
        "recoverable": recoverable,
    }


def _ensure_fields(payload: dict, required_fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in required_fields if field not in payload]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{label} missing required field(s): {joined}")


def _validate_context(context: dict) -> None:
    _ensure_fields(context, REQUIRED_CONTEXT_FIELDS, "context")
    window_box = context["window_box"]
    if not isinstance(window_box, list) or len(window_box) != 4:
        raise ValueError("context.window_box must be a 4-item list")


def _validate_v1_start(payload: dict) -> None:
    if payload.get("protocol_version") != "v1":
        raise ValueError("session.start must use protocol_version='v1'")

    if payload.get("event") != "session.start":
        raise ValueError("payload event must be session.start")

    _ensure_fields(payload, REQUIRED_V1_COMMON_FIELDS + REQUIRED_V1_START_FIELDS, "payload")
    _validate_context(payload["context"])


def _normalize_legacy_screenshot(payload: dict) -> dict:
    rect = payload.get("windowRect") or {}
    return {
        "protocol_version": "legacy",
        "event": "session.start",
        "trace_id": payload.get("trace_id", "legacy-trace"),
        "session_id": payload.get("session_id", "legacy-session"),
        "goal": payload.get("task", ""),
        "context": {
            "process_name": payload.get("process_name", "legacy-client"),
            "window_title": payload.get("window_title", ""),
            "dpi_scale": payload.get("dpi_scale", 1.0),
            "window_box": [
                rect.get("left", 0),
                rect.get("top", 0),
                rect.get("width", 0),
                rect.get("height", 0),
            ],
        },
        "image_base64": payload.get("data", ""),
    }


def normalize_client_message(payload: dict) -> dict:
    if payload.get("event") == "session.start":
        _validate_v1_start(payload)
        return payload

    if payload.get("type") == "screenshot":
        return _normalize_legacy_screenshot(payload)

    raise ValueError("unsupported client payload")
