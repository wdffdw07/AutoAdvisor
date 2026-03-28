from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from services.tutorial_contracts import validate_plan, validate_step


LEGACY_REGION = "active-window"


class PlannerService:
    def __init__(self, agent_factory: Callable[[], Any]):
        self._agent_factory = agent_factory

    async def initial_plan(self, goal: str, screenshot_ref: str, surface_context: dict) -> dict:
        agent = self._agent_factory()

        if hasattr(agent, "build_initial_tutorial_plan"):
            raw_plan = await agent.build_initial_tutorial_plan(
                base64_image=screenshot_ref,
                user_goal=goal,
                surface_context=surface_context,
            )
        elif hasattr(agent, "plan_steps"):
            raw_plan = await agent.plan_steps(
                base64_image=screenshot_ref,
                user_goal=goal,
            )
        else:
            raise ValueError("planner agent does not expose a planning interface")

        normalized = self._normalize_plan(raw_plan, goal=goal, surface_context=surface_context)
        return validate_plan(normalized)

    async def step_retarget(
        self,
        current_step: dict,
        screenshot_ref: str,
        candidates: list[dict],
        failure_packet: dict,
    ) -> dict:
        agent = self._agent_factory()

        if hasattr(agent, "retarget_tutorial_step"):
            raw_decision = await agent.retarget_tutorial_step(
                current_step=current_step,
                base64_image=screenshot_ref,
                candidates=candidates,
                failure_packet=failure_packet,
            )
        else:
            raw_decision = self._fallback_retarget(current_step, candidates)

        return self._validate_retarget_decision(current_step, raw_decision)

    async def partial_replan(
        self,
        goal: str,
        completed_steps: list[dict],
        failed_step: dict,
        screenshot_ref: str,
        failure_packet: dict,
    ) -> dict:
        agent = self._agent_factory()

        if hasattr(agent, "replan_remaining_steps"):
            raw_decision = await agent.replan_remaining_steps(
                user_goal=goal,
                completed_steps=completed_steps,
                failed_step=failed_step,
                base64_image=screenshot_ref,
                failure_packet=failure_packet,
            )
        else:
            raw_decision = {
                "decision": "replace_remaining_steps",
                "start_from_failed_step": failed_step["id"],
                "new_steps": self._normalize_plan(
                    await agent.plan_steps(base64_image=screenshot_ref, user_goal=goal),
                    goal=goal,
                    surface_context={},
                )["steps"],
            }

        return self._validate_partial_replan_decision(raw_decision, goal=goal)

    async def full_replan(
        self,
        goal: str,
        trusted_history: list[dict],
        screenshot_ref: str,
        failure_packet: dict,
    ) -> dict:
        agent = self._agent_factory()

        if hasattr(agent, "replan_from_current_state"):
            raw_decision = await agent.replan_from_current_state(
                user_goal=goal,
                trusted_history=trusted_history,
                base64_image=screenshot_ref,
                failure_packet=failure_packet,
            )
        else:
            raw_decision = {
                "decision": "replace_entire_active_plan",
                "new_plan": self._normalize_plan(
                    await agent.plan_steps(base64_image=screenshot_ref, user_goal=goal),
                    goal=goal,
                    surface_context={},
                ),
            }

        return self._validate_full_replan_decision(raw_decision)

    def _normalize_plan(self, raw_plan: dict, goal: str, surface_context: dict) -> dict:
        plan = deepcopy(raw_plan) if isinstance(raw_plan, dict) else {}
        raw_steps = plan.get("steps") or []

        return {
            "goal": str(plan.get("goal") or goal),
            "steps": [
                self._normalize_step(step, index + 1, surface_context)
                for index, step in enumerate(raw_steps)
            ],
        }

    def _normalize_step(self, step: dict, index: int, surface_context: dict) -> dict:
        if isinstance(step, dict) and "target" in step and "instruction" in step:
            normalized = deepcopy(step)
            normalized.setdefault("id", f"step_{index}")
            normalized.setdefault("title", normalized["instruction"])
            if normalized.get("action") and not normalized.get("action_family"):
                normalized["action_family"] = normalized["action"]
            normalized.setdefault("recovery_hints", {})
            normalized.setdefault("critical", False)
            return normalized

        action = step.get("action", "click") if isinstance(step, dict) else "click"
        description = step.get("description") or step.get("tooltip") or f"Step {index}" if isinstance(step, dict) else f"Step {index}"
        require_manual_next = bool(step.get("require_manual_next", action in {"input_text", "drag", "wait"})) if isinstance(step, dict) else False

        hints = {
            "region": LEGACY_REGION,
            "text": [description],
        }
        if surface_context.get("kind"):
            hints["surface_kind"] = surface_context["kind"]

        return {
            "id": f"step_{index}",
            "title": description,
            "instruction": description,
            "action_family": action,
            "critical": require_manual_next,
            "target": {
                "kind": "region_only",
                "hints": hints,
            },
            "success_criteria": [{"type": "user_confirmed"}],
            "recovery_hints": {},
            "window_expectation": {"relation": "stay_on_current"},
        }

    def _fallback_retarget(self, current_step: dict, candidates: list[dict]) -> dict:
        if candidates:
            return {
                "decision": "select_candidate",
                "step_id": current_step["id"],
                "candidate_ids": [candidates[0]["id"]],
            }

        return {
            "decision": "request_partial_replan",
            "step_id": current_step["id"],
            "reason": "no candidates were available for the current step",
        }

    def _validate_retarget_decision(self, current_step: dict, decision: dict) -> dict:
        if not isinstance(decision, dict):
            raise ValueError("step_retarget must return a dictionary")

        decision_type = decision.get("decision")
        normalized = deepcopy(decision)

        if decision_type == "select_candidate":
            candidate_ids = normalized.get("candidate_ids")
            if not isinstance(candidate_ids, list) or not candidate_ids:
                raise ValueError("select_candidate requires candidate_ids")
            return normalized

        if decision_type == "refine_target":
            patched_step = deepcopy(current_step)
            if "target_patch" in normalized:
                patched_step["target"] = normalized["target_patch"]
            if "instruction_patch" in normalized:
                patched_step["instruction"] = normalized["instruction_patch"]
                patched_step["title"] = normalized["instruction_patch"]
            validate_step(patched_step)
            return normalized

        if decision_type == "request_partial_replan":
            if not normalized.get("reason"):
                raise ValueError("request_partial_replan requires a reason")
            return normalized

        raise ValueError("step_retarget returned an unsupported decision")

    def _validate_partial_replan_decision(self, decision: dict, goal: str) -> dict:
        if not isinstance(decision, dict):
            raise ValueError("partial_replan must return a dictionary")
        if decision.get("decision") != "replace_remaining_steps":
            raise ValueError("partial_replan must return replace_remaining_steps")

        normalized = deepcopy(decision)
        new_steps = normalized.get("new_steps") or []
        normalized["new_steps"] = [validate_step(step) for step in new_steps]
        normalized.setdefault("goal", goal)
        return normalized

    def _validate_full_replan_decision(self, decision: dict) -> dict:
        if not isinstance(decision, dict):
            raise ValueError("full_replan must return a dictionary")
        if decision.get("decision") != "replace_entire_active_plan":
            raise ValueError("full_replan must return replace_entire_active_plan")

        normalized = deepcopy(decision)
        normalized["new_plan"] = validate_plan(normalized.get("new_plan") or {})
        return normalized

