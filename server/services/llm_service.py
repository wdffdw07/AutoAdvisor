from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from services.planner_service import PlannerService
from services.tutorial_runtime import TutorialRuntime


MANUAL_ACTIONS = {"input_text", "drag", "wait", "text", "scroll", "observe"}


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


class AgentGrounder:
    def __init__(self, agent_factory: Callable[[], Any]):
        self._agent_factory = agent_factory

    async def locate(self, step: dict, snapshot: dict) -> dict:
        return await self._analyze(step, snapshot)

    async def observe(self, step: dict, snapshot: dict) -> dict:
        return await self._analyze(step, snapshot)

    async def _analyze(self, step: dict, snapshot: dict) -> dict:
        agent = self._agent_factory()
        result = await agent.analyze_screenshot(
            base64_image=snapshot.get("image_base64", ""),
            user_goal=step.get("instruction") or step.get("title") or "",
        )

        action = result.get("action", "click")
        box = result.get("box")
        tooltip = result.get("tooltip") or step.get("instruction") or step.get("title") or action
        reason = result.get("reason", "")

        if action == "complete":
            return {
                "status": "ok",
                "signals": {"element_appeared": True},
                "targets": {},
                "tooltip": tooltip,
                "reason": reason,
            }

        if box:
            return {
                "status": "ok",
                "signals": {"element_appeared": True},
                "targets": {
                    "primary": {
                        "label": tooltip,
                        "bbox": box,
                        "confidence": 0.8,
                    }
                },
                "tooltip": tooltip,
                "reason": reason,
            }

        return {
            "status": "not_found",
            "targets": {},
            "tooltip": tooltip,
            "reason": reason,
        }


class LLMSessionService:
    def __init__(
        self,
        agent_factory: Callable[[], Any],
        planner_factory: Callable[[], Any] | None = None,
        grounder_factory: Callable[[], Any] | None = None,
        runtime_factory: Callable[[Any, Any], Any] | None = None,
    ):
        self._agent_factory = agent_factory
        self._planner_factory = planner_factory or (lambda: PlannerService(agent_factory))
        self._grounder_factory = grounder_factory or (lambda: AgentGrounder(agent_factory))
        self._runtime_factory = runtime_factory or (lambda planner, grounder: TutorialRuntime(planner=planner, grounder=grounder))
        self._runtimes: dict[str, Any] = {}

    async def start_session(self, session_state, message: dict) -> list[dict]:
        runtime = self._runtime_factory(self._planner_factory(), self._grounder_factory())
        self._runtimes[session_state.session_id] = runtime

        goal = message.get("goal") or session_state.goal
        events = await runtime.start(goal, self._snapshot_from_message(message, session_state.context))
        translated = self._translate_events(runtime, events)
        self._sync_session_state(session_state, runtime)
        return translated

    async def advance_session(self, session_state, message: dict) -> list[dict]:
        runtime = self._ensure_runtime(session_state, message)
        events = await runtime.observe(self._snapshot_from_message(message, session_state.context))
        translated = self._translate_events(runtime, events)
        self._sync_session_state(session_state, runtime)
        return translated

    async def confirm_session(self, session_state, message: dict | None = None) -> list[dict]:
        runtime = self._runtimes.get(session_state.session_id)
        if runtime is None:
            return []

        events = await runtime.confirm_checkpoint()
        translated = self._translate_events(runtime, events)
        self._sync_session_state(session_state, runtime)
        return translated

    async def complete_session(self, session_state, message: dict) -> list[dict]:
        runtime = self._ensure_runtime(session_state, message)
        summary = message.get("summary") or session_state.plan_summary or "Guide completed"
        events = await runtime.complete(summary)
        translated = self._translate_events(runtime, events)
        self._sync_session_state(session_state, runtime)
        return translated

    def _ensure_runtime(self, session_state, message: dict):
        runtime = self._runtimes.get(session_state.session_id)
        if runtime is None:
            runtime = self._runtime_factory(self._planner_factory(), self._grounder_factory())
            self._runtimes[session_state.session_id] = runtime
            snapshot = self._snapshot_from_message(message, session_state.context)
            runtime.goal = message.get("goal") or session_state.goal
            runtime.current_snapshot = deepcopy(snapshot)
        return runtime

    def _snapshot_from_message(self, message: dict, fallback_context: dict) -> dict:
        context = deepcopy(message.get("context") or fallback_context or {})
        surface = deepcopy(message.get("surface") or {
            "kind": context.get("window_kind", "main"),
            "process_name": context.get("process_name", ""),
            "window_title": context.get("window_title", ""),
        })
        return {
            "image_base64": message.get("image_base64", ""),
            "context": context,
            "surface": surface,
        }

    def _sync_session_state(self, session_state, runtime) -> None:
        session_state.goal = runtime.goal or session_state.goal
        if runtime.current_snapshot.get("context"):
            session_state.context = deepcopy(runtime.current_snapshot["context"])
        session_state.done = runtime.is_done()
        session_state.step_index = runtime.step_index
        session_state.plan_steps = self._compat_plan_steps(runtime)
        session_state.plan_summary = runtime.plan_summary

    def _compat_plan_steps(self, runtime) -> list[dict]:
        compat_steps = []
        for index, step in enumerate(runtime.transport_plan_steps(), start=1):
            current = dict(step)
            current["step_id"] = f"s-{index:03d}"
            compat_steps.append(current)
        return compat_steps

    def _compat_step_id_map(self, runtime) -> dict[str, str]:
        return {
            step.get("step_id") or step.get("id"): f"s-{index:03d}"
            for index, step in enumerate(runtime.transport_plan_steps(), start=1)
        }

    def _translate_events(self, runtime, events: list[dict]) -> list[dict]:
        step_id_map = self._compat_step_id_map(runtime)
        compat_steps = self._compat_plan_steps(runtime)
        translated = []

        for event in events:
            current = dict(event)
            if current.get("event") == "plan.ready":
                current["steps"] = compat_steps
            if current.get("step_id") in step_id_map:
                current["step_id"] = step_id_map[current["step_id"]]
            translated.append(current)

        return translated
