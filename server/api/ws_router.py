from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_V1_COMMON_FIELDS = ("trace_id", "session_id")
REQUIRED_V1_START_FIELDS = ("goal", "context", "image_base64")
REQUIRED_V1_UPDATE_FIELDS = ("context", "image_base64")
REQUIRED_CONTEXT_FIELDS = ("process_name", "window_title", "dpi_scale", "window_box")


@dataclass
class SessionState:
    session_id: str
    goal: str
    protocol_version: str
    context: dict
    step_index: int = 0
    waiting_for_manual: bool = False
    done: bool = False

    @classmethod
    def from_start(cls, payload: dict) -> "SessionState":
        return cls(
            session_id=payload["session_id"],
            goal=payload.get("goal", ""),
            protocol_version=payload.get("protocol_version", "v1"),
            context=payload["context"],
        )


def build_session_error(
    code: str,
    message: str,
    recoverable: bool,
    trace_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    event = {
        "protocol_version": "v1",
        "event": "session.error",
        "code": code,
        "message": message,
        "recoverable": recoverable,
    }
    if trace_id is not None:
        event["trace_id"] = trace_id
    if session_id is not None:
        event["session_id"] = session_id
    return event


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


def _validate_v1_event(payload: dict, event_name: str, required_fields: tuple[str, ...]) -> None:
    if payload.get("protocol_version") != "v1":
        raise ValueError(f"{event_name} must use protocol_version='v1'")

    if payload.get("event") != event_name:
        raise ValueError(f"payload event must be {event_name}")

    _ensure_fields(payload, REQUIRED_V1_COMMON_FIELDS + required_fields, "payload")


def _validate_v1_start(payload: dict) -> None:
    _validate_v1_event(payload, "session.start", REQUIRED_V1_START_FIELDS)
    _validate_context(payload["context"])


def _validate_v1_update(payload: dict) -> None:
    _validate_v1_event(payload, "context.update", REQUIRED_V1_UPDATE_FIELDS)
    _validate_context(payload["context"])


def _validate_v1_user_next(payload: dict) -> None:
    _validate_v1_event(payload, "user.next", ())


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
    event_name = payload.get("event")
    if event_name == "session.start":
        _validate_v1_start(payload)
        return payload

    if event_name == "context.update":
        _validate_v1_update(payload)
        return payload

    if event_name == "user.next":
        _validate_v1_user_next(payload)
        return payload

    if payload.get("type") == "screenshot":
        return _normalize_legacy_screenshot(payload)

    raise ValueError("unsupported client payload")


def _stamp_events(events: list[dict], trace_id: str, session_id: str) -> list[dict]:
    stamped = []
    for event in events:
        current = dict(event)
        current.setdefault("trace_id", trace_id)
        current.setdefault("session_id", session_id)
        stamped.append(current)
    return stamped


def _update_session_flags(session_state: SessionState, events: list[dict]) -> None:
    session_state.waiting_for_manual = False
    for event in events:
        if event["event"] == "session.done":
            session_state.done = True
        if event["event"] == "guide.wait_manual":
            session_state.waiting_for_manual = True
        if event["event"] == "guide.highlight" and event.get("require_manual_next"):
            session_state.waiting_for_manual = True


def _legacy_response_from_events(events: list[dict]) -> dict:
    plan = next((event for event in events if event["event"] == "plan.step"), None)
    guide = next(
        (
            event
            for event in events
            if event["event"] in {"guide.highlight", "guide.wait_manual", "session.done", "session.error"}
        ),
        None,
    )

    if guide is None:
        return {"action": "none", "tooltip": "No guidance available"}

    if guide["event"] == "session.error":
        return {
            "action": "error",
            "tooltip": guide["message"],
            "error": guide["code"],
        }

    if guide["event"] == "session.done":
        return {
            "action": "complete",
            "tooltip": guide["summary"],
        }

    action = plan["action"] if plan is not None else "wait"
    response = {
        "action": action,
        "tooltip": guide.get("tooltip", ""),
    }

    if guide["event"] == "guide.highlight":
        response["box"] = guide["target"]["relative_box"]

    return response


async def handle_client_payload(
    payload: dict,
    session_state: SessionState | None,
    service: Any,
) -> tuple[SessionState | None, list[dict]]:
    trace_id = payload.get("trace_id", "server-trace") if isinstance(payload, dict) else "server-trace"
    inbound_session_id = payload.get("session_id") if isinstance(payload, dict) else None

    try:
        normalized = normalize_client_message(payload)
    except ValueError as error:
        return session_state, [
            build_session_error(
                "E_BAD_REQUEST",
                str(error),
                recoverable=False,
                trace_id=trace_id,
                session_id=inbound_session_id or (session_state.session_id if session_state else None),
            )
        ]

    event_name = normalized["event"]
    session_id = normalized.get("session_id") or (session_state.session_id if session_state else None)

    if normalized.get("protocol_version") == "legacy" and session_state is not None and event_name == "session.start":
        normalized = dict(normalized)
        normalized["event"] = "context.update"
        normalized["session_id"] = session_state.session_id
        event_name = "context.update"
        session_id = session_state.session_id

    if event_name == "session.start":
        session_state = SessionState.from_start(normalized)
        session_id = session_state.session_id
        events = await service.start_session(session_state, normalized)
    elif session_state is None:
        return session_state, [
            build_session_error(
                "E_BAD_REQUEST",
                "session has not started",
                recoverable=False,
                trace_id=trace_id,
                session_id=session_id,
            )
        ]
    elif event_name == "user.next":
        session_state.waiting_for_manual = False
        return session_state, []
    elif event_name == "context.update":
        events = await service.advance_session(session_state, normalized)
    else:
        return session_state, [
            build_session_error(
                "E_BAD_REQUEST",
                f"unsupported event: {event_name}",
                recoverable=False,
                trace_id=trace_id,
                session_id=session_id,
            )
        ]

    stamped = _stamp_events(events, trace_id=trace_id, session_id=session_id)
    _update_session_flags(session_state, stamped)

    if session_state.protocol_version == "legacy":
        return session_state, [_legacy_response_from_events(stamped)]

    return session_state, stamped
