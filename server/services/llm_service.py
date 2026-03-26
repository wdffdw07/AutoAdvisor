from __future__ import annotations

from typing import Any, Callable


MANUAL_ACTIONS = {"input_text", "drag", "wait"}
DEFAULT_TOTAL_STEPS = 3


def adapt_agent_response(agent_result: dict, step_id: str, total_steps: int) -> list[dict]:
    action = agent_result.get("action", "click")
    tooltip = agent_result.get("tooltip", "")
    reason = agent_result.get("reason", "")

    events = [
        {
            "protocol_version": "v1",
            "event": "plan.step",
            "step_id": step_id,
            "total_steps": total_steps,
            "action": action,
            "description": tooltip or action,
            "reason": reason,
        }
    ]

    if action == "complete":
        events.append(
            {
                "protocol_version": "v1",
                "event": "session.done",
                "summary": tooltip or "Done",
            }
        )
        return events

    box = agent_result.get("box")
    if box:
        events.append(
            {
                "protocol_version": "v1",
                "event": "guide.highlight",
                "step_id": step_id,
                "target": {"relative_box": box, "confidence": 0.8},
                "tooltip": tooltip,
                "require_manual_next": action in MANUAL_ACTIONS,
            }
        )
    else:
        events.append(
            {
                "protocol_version": "v1",
                "event": "guide.wait_manual",
                "step_id": step_id,
                "tooltip": tooltip or "Continue when ready",
            }
        )

    return events


class LLMSessionService:
    def __init__(self, agent_factory: Callable[[], Any], total_steps: int = DEFAULT_TOTAL_STEPS):
        self._agent_factory = agent_factory
        self._total_steps = total_steps

    async def start_session(self, session_state, message: dict) -> list[dict]:
        session_state.goal = message.get("goal") or session_state.goal
        session_state.context = message.get("context") or session_state.context
        return await self._analyze(session_state, message)

    async def advance_session(self, session_state, message: dict) -> list[dict]:
        session_state.context = message.get("context") or session_state.context
        session_state.goal = message.get("goal") or session_state.goal
        return await self._analyze(session_state, message)

    async def _analyze(self, session_state, message: dict) -> list[dict]:
        agent = self._agent_factory()
        session_state.step_index += 1

        step_id = f"s-{session_state.step_index:03d}"
        result = await agent.analyze_screenshot(
            base64_image=message.get("image_base64", ""),
            user_goal=session_state.goal or "",
        )

        return adapt_agent_response(
            result,
            step_id=step_id,
            total_steps=self._total_steps,
        )
