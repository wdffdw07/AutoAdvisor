from __future__ import annotations

from typing import Any, Callable


MANUAL_ACTIONS = {"input_text", "drag", "wait"}


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


def _normalize_plan_step(step: dict, index: int) -> dict:
    action = step.get("action", "click")
    description = step.get("description") or step.get("tooltip") or f"Step {index}"
    reason = step.get("reason", "")
    require_manual_next = bool(step.get("require_manual_next", action in MANUAL_ACTIONS))

    return {
        "step_id": f"s-{index:03d}",
        "action": action,
        "description": description,
        "reason": reason,
        "require_manual_next": require_manual_next,
    }


def _build_plan_ready_event(plan_steps: list[dict], current_step_index: int, summary: str) -> dict:
    return {
        "protocol_version": "v1",
        "event": "plan.ready",
        "summary": summary,
        "total_steps": len(plan_steps),
        "current_step_index": current_step_index,
        "steps": [dict(step) for step in plan_steps],
    }


def _build_plan_step_event(plan_step: dict, total_steps: int) -> dict:
    return {
        "protocol_version": "v1",
        "event": "plan.step",
        "step_id": plan_step["step_id"],
        "total_steps": total_steps,
        "action": plan_step["action"],
        "description": plan_step["description"],
        "reason": plan_step["reason"],
    }


def _build_done_event(summary: str) -> dict:
    return {
        "protocol_version": "v1",
        "event": "session.done",
        "summary": summary or "Guide completed",
    }


def _build_remaining_plan_goal(session_state) -> str:
    completed_steps = session_state.plan_steps[:session_state.step_index]
    completed_text = "\n".join(
        f"{index + 1}. {step['description']}"
        for index, step in enumerate(completed_steps)
    )

    suffix = "\nReturn only the remaining steps from the current screenshot. Do not mark the task complete unless it is visibly done."
    if completed_text:
        return f"{session_state.goal}\nCompleted steps:\n{completed_text}{suffix}"
    return f"{session_state.goal}{suffix}"


def _merge_locator_events(locator_result: dict, plan_step: dict, total_steps: int) -> list[dict]:
    action = locator_result.get("action") or plan_step["action"]
    tooltip = locator_result.get("tooltip") or plan_step["description"]
    reason = plan_step.get("reason") or locator_result.get("reason", "")

    if action == "complete":
        return [_build_done_event(tooltip)]

    events = [
        {
            "protocol_version": "v1",
            "event": "plan.step",
            "step_id": plan_step["step_id"],
            "total_steps": total_steps,
            "action": plan_step["action"],
            "description": plan_step["description"],
            "reason": reason,
        }
    ]

    box = locator_result.get("box")
    if box:
        events.append(
            {
                "protocol_version": "v1",
                "event": "guide.highlight",
                "step_id": plan_step["step_id"],
                "target": {"relative_box": box, "confidence": 0.8},
                "tooltip": tooltip,
                "require_manual_next": plan_step["require_manual_next"],
            }
        )
    else:
        events.append(
            {
                "protocol_version": "v1",
                "event": "guide.wait_manual",
                "step_id": plan_step["step_id"],
                "tooltip": tooltip or "Continue when ready",
            }
        )

    return events


class LLMSessionService:
    def __init__(self, agent_factory: Callable[[], Any]):
        self._agent_factory = agent_factory

    async def start_session(self, session_state, message: dict) -> list[dict]:
        session_state.goal = message.get("goal") or session_state.goal
        session_state.context = message.get("context") or session_state.context
        session_state.done = False
        session_state.step_index = 0

        if not session_state.plan_steps:
            session_state.plan_summary, session_state.plan_steps = await self._build_plan(session_state, message)

        return await self._emit_current_step(session_state, message, include_plan_ready=True)

    async def advance_session(self, session_state, message: dict) -> list[dict]:
        session_state.context = message.get("context") or session_state.context
        session_state.goal = message.get("goal") or session_state.goal
        if session_state.done:
            return [_build_done_event(session_state.plan_summary or "Guide completed")]

        if not session_state.plan_steps:
            session_state.plan_summary, session_state.plan_steps = await self._build_plan(session_state, message)

        session_state.step_index += 1
        if session_state.step_index >= len(session_state.plan_steps):
            extended = await self._extend_plan(session_state, message)
            if not extended:
                session_state.done = True
                return [_build_done_event(session_state.plan_summary or "Guide completed")]
            return await self._emit_current_step(session_state, message, include_plan_ready=True)

        return await self._emit_current_step(session_state, message)

    async def complete_session(self, session_state, message: dict) -> list[dict]:
        session_state.goal = message.get("goal") or session_state.goal
        session_state.done = True
        summary = message.get("summary") or session_state.plan_summary or "Guide completed"
        return [_build_done_event(summary)]

    async def _build_plan(self, session_state, message: dict) -> tuple[str, list[dict]]:
        agent = self._agent_factory()

        if hasattr(agent, "plan_steps"):
            raw_plan = await agent.plan_steps(
                base64_image=message.get("image_base64", ""),
                user_goal=session_state.goal or "",
            )
            raw_steps = raw_plan.get("steps") or []
            summary = raw_plan.get("summary") or session_state.goal or "Guide plan"
        else:
            fallback_result = await agent.analyze_screenshot(
                base64_image=message.get("image_base64", ""),
                user_goal=session_state.goal or "",
            )
            raw_steps = [fallback_result]
            summary = session_state.goal or "Guide plan"

        plan_steps = [_normalize_plan_step(step, index + 1) for index, step in enumerate(raw_steps)]

        if not plan_steps:
            plan_steps = [_normalize_plan_step({"action": "click", "description": session_state.goal or "Continue"}, 1)]

        return summary, plan_steps

    async def _extend_plan(self, session_state, message: dict) -> bool:
        agent = self._agent_factory()
        raw_steps: list[dict] = []

        if hasattr(agent, "plan_steps"):
            raw_plan = await agent.plan_steps(
                base64_image=message.get("image_base64", ""),
                user_goal=_build_remaining_plan_goal(session_state),
            )
            raw_steps = raw_plan.get("steps") or []
        else:
            fallback_result = await agent.analyze_screenshot(
                base64_image=message.get("image_base64", ""),
                user_goal=session_state.goal or "",
            )
            if fallback_result.get("action") == "complete":
                return False
            raw_steps = [fallback_result]

        normalized_steps = [
            _normalize_plan_step(step, len(session_state.plan_steps) + index + 1)
            for index, step in enumerate(raw_steps)
        ]

        if not normalized_steps:
            return False

        session_state.plan_steps.extend(normalized_steps)
        return True

    async def _emit_current_step(self, session_state, message: dict, include_plan_ready: bool = False) -> list[dict]:
        agent = self._agent_factory()
        current_step = session_state.plan_steps[session_state.step_index]
        analysis_goal = session_state.goal or ""
        if current_step["description"]:
            analysis_goal = f"{analysis_goal}\nCurrent planned step: {current_step['description']}"

        locator_result = await agent.analyze_screenshot(
            base64_image=message.get("image_base64", ""),
            user_goal=analysis_goal,
        )

        total_steps = len(session_state.plan_steps)
        events: list[dict] = []

        if include_plan_ready:
            events.append(
                _build_plan_ready_event(
                    session_state.plan_steps,
                    current_step_index=session_state.step_index + 1,
                    summary=session_state.plan_summary,
                )
            )

        events.extend(_merge_locator_events(locator_result, current_step, total_steps))

        if events and events[-1]["event"] == "session.done":
            session_state.done = True

        return events
