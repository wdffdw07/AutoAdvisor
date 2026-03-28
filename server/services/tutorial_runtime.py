from __future__ import annotations

from copy import deepcopy
from inspect import isawaitable
from typing import Any

from services.failure_packets import (
    append_recovery_action,
    begin_failure_episode,
    build_failure_packet,
)


class TutorialRuntime:
    def __init__(
        self,
        planner: Any,
        grounder: Any,
        *,
        no_progress_full_replan_limit: int = 2,
    ):
        self._planner = planner
        self._grounder = grounder
        self._no_progress_full_replan_limit = no_progress_full_replan_limit
        self._reset()

    def _reset(self) -> None:
        self.goal = ""
        self.plan = {"goal": "", "steps": []}
        self.plan_summary = ""
        self.phase = "idle"
        self.step_phase = "idle"
        self.step_index = 0
        self.completed_steps: list[dict] = []
        self.failure_episodes: list[dict] = []
        self.current_snapshot: dict = {}
        self._local_retry_count = 0
        self._checkpoint_confirmed = False
        self._no_progress_full_replans = 0
        self._last_full_replan_progress_count = 0

    async def start(self, goal: str, snapshot: dict) -> list[dict]:
        self._reset()
        self.goal = goal
        self.current_snapshot = deepcopy(snapshot or {})
        self.phase = "planning"

        self.plan = await self._planner.initial_plan(
            goal,
            self._screenshot_ref(self.current_snapshot),
            self._surface_context(self.current_snapshot),
        )
        self.plan_summary = self.plan.get("goal") or goal
        self.phase = "running"

        if not self.plan.get("steps"):
            self.phase = "done"
            return [self._build_done_event(self.plan_summary or "Guide completed")]

        return await self._locate_current_step(include_plan_ready=True)

    async def observe(self, snapshot: dict) -> list[dict]:
        self.current_snapshot = deepcopy(snapshot or {})

        if self.phase == "done":
            return [self._build_done_event(self.plan_summary or "Guide completed")]
        if self.phase == "blocked":
            return [self._build_blocked_event("tutorial runtime is blocked")]
        if not self.plan.get("steps"):
            self.phase = "done"
            return [self._build_done_event(self.plan_summary or "Guide completed")]

        self.step_phase = "observing"
        current_step = self._current_step()
        observation = await self._call_grounder("observe", current_step)
        if self._is_step_successful(current_step, observation):
            return await self._advance_after_success()

        return await self._recover_from_failure(current_step, observation)

    async def confirm_checkpoint(self) -> list[dict]:
        if self.phase != "running":
            return []

        self._checkpoint_confirmed = True
        self.step_phase = "observing"
        return []

    async def complete(self, summary: str | None = None) -> list[dict]:
        self.phase = "done"
        self.step_phase = "idle"
        return [self._build_done_event(summary or self.plan_summary or "Guide completed")]

    def transport_plan_steps(self) -> list[dict]:
        return [self._transport_step(step) for step in self.plan.get("steps") or []]

    def is_done(self) -> bool:
        return self.phase == "done"

    def _current_step(self) -> dict:
        return self.plan["steps"][self.step_index]

    async def _call_grounder(self, method_name: str, step: dict) -> dict:
        result = getattr(self._grounder, method_name)(step, self.current_snapshot)
        if isawaitable(result):
            result = await result
        return result or {"status": "not_found", "targets": {}}

    async def _locate_current_step(self, *, include_plan_ready: bool) -> list[dict]:
        current_step = self._current_step()
        self.step_phase = "locating"
        locate_result = await self._call_grounder("locate", current_step)
        return self._build_guidance_events(current_step, locate_result, include_plan_ready=include_plan_ready)

    def _build_guidance_events(self, step: dict, locate_result: dict, *, include_plan_ready: bool) -> list[dict]:
        events: list[dict] = []
        if include_plan_ready:
            events.append(self._build_plan_ready_event())

        transport_step = self._transport_step(step)
        events.append(self._build_plan_step_event(transport_step))

        box = self._primary_box(locate_result)
        if box:
            self.step_phase = "checkpoint_wait" if step.get("critical") else "guiding"
            events.append(
                {
                    "protocol_version": "v1",
                    "event": "guide.highlight",
                    "step_id": transport_step["step_id"],
                    "target": {"relative_box": box, "confidence": self._primary_confidence(locate_result)},
                    "tooltip": locate_result.get("tooltip") or step.get("instruction", transport_step["description"]),
                    "require_manual_next": bool(step.get("critical", False)),
                }
            )
            return events

        self.step_phase = "checkpoint_wait" if step.get("critical") else "guiding"
        events.append(
            {
                "protocol_version": "v1",
                "event": "guide.wait_manual",
                "step_id": transport_step["step_id"],
                "tooltip": locate_result.get("tooltip") or step.get("instruction", transport_step["description"]),
            }
        )
        return events

    async def _advance_after_success(self) -> list[dict]:
        current_step = deepcopy(self._current_step())
        self.completed_steps.append(current_step)
        self.step_phase = "step_done"
        self.step_index += 1
        self._local_retry_count = 0
        self._checkpoint_confirmed = False
        self._no_progress_full_replans = 0
        self._last_full_replan_progress_count = len(self.completed_steps)

        if self.step_index >= len(self.plan.get("steps") or []):
            if await self._extend_plan_if_needed():
                return await self._locate_current_step(include_plan_ready=True)
            self.phase = "done"
            self.step_phase = "idle"
            return [self._build_done_event(self.plan_summary or "Guide completed")]

        return await self._locate_current_step(include_plan_ready=False)

    async def _extend_plan_if_needed(self) -> bool:
        try:
            decision = await self._planner.full_replan(
                goal=self.goal,
                trusted_history=self._recent_progress_context(),
                screenshot_ref=self._screenshot_ref(self.current_snapshot),
                failure_packet={
                    "reason": "plan_exhausted",
                    "recent_progress_context": self._recent_progress_context(),
                },
            )
        except Exception:
            return False

        new_plan = deepcopy(decision.get("new_plan") or {})
        new_steps = deepcopy(new_plan.get("steps") or [])
        if not new_steps:
            return False

        self.plan_summary = new_plan.get("goal") or self.plan_summary or self.goal
        self.plan.setdefault("steps", []).extend(self._uniquify_new_steps(new_steps))
        return True

    async def _recover_from_failure(self, step: dict, observation: dict) -> list[dict]:
        self.step_phase = "recovering"
        episode = begin_failure_episode(
            step["id"],
            observation.get("status") or "grounding_failed",
            self._failure_snapshot(step, observation),
        )
        self.failure_episodes.append(episode)

        retry_budget = int(step.get("recovery_hints", {}).get("retry_budget", 1))
        if self._local_retry_count < retry_budget:
            self._local_retry_count += 1
            append_recovery_action(episode, "local_retry", "retrying")
            locate_result = await self._call_grounder("locate", step)
            if locate_result.get("status") in {"ok", "ambiguous"}:
                append_recovery_action(episode, "local_retry", "recovered")
                return self._build_guidance_events(step, locate_result, include_plan_ready=False)
            append_recovery_action(episode, "local_retry", "still_not_found")
            observation = locate_result

        failure_packet = build_failure_packet(
            self._current_step_summary(step),
            self.failure_episodes,
            self._recent_progress_context(),
        )
        candidates = self._flatten_candidates(observation)
        decision = await self._planner.step_retarget(
            current_step=step,
            screenshot_ref=self._screenshot_ref(self.current_snapshot),
            candidates=candidates,
            failure_packet=failure_packet,
        )

        decision_type = decision.get("decision")
        if decision_type == "select_candidate":
            append_recovery_action(episode, "step_retarget", "candidate_selected")
            return self._emit_selected_candidate(step, candidates, decision.get("candidate_ids") or [])

        if decision_type == "refine_target":
            append_recovery_action(episode, "step_retarget", "target_refined")
            self._apply_target_patch(step, decision)
            self._local_retry_count = 0
            return await self._locate_current_step(include_plan_ready=False)

        append_recovery_action(episode, "step_retarget", "partial_replan_requested")
        return await self._apply_partial_replan(step, failure_packet)

    async def _apply_partial_replan(self, failed_step: dict, failure_packet: dict) -> list[dict]:
        try:
            decision = await self._planner.partial_replan(
                goal=self.goal,
                completed_steps=deepcopy(self.completed_steps),
                failed_step=deepcopy(failed_step),
                screenshot_ref=self._screenshot_ref(self.current_snapshot),
                failure_packet=failure_packet,
            )
        except Exception:
            return await self._apply_full_replan(failure_packet)

        new_steps = deepcopy(decision.get("new_steps") or [])
        self.plan["steps"] = deepcopy(self.completed_steps) + self._uniquify_new_steps(new_steps, prefix_existing=False)
        self.step_index = len(self.completed_steps)
        self._local_retry_count = 0
        self._checkpoint_confirmed = False

        if self.step_index >= len(self.plan.get("steps") or []):
            self.phase = "done"
            self.step_phase = "idle"
            return [self._build_done_event(self.plan_summary or "Guide completed")]

        return await self._locate_current_step(include_plan_ready=True)

    async def _apply_full_replan(self, failure_packet: dict) -> list[dict]:
        trusted_history = self._recent_progress_context()
        decision = await self._planner.full_replan(
            goal=self.goal,
            trusted_history=trusted_history,
            screenshot_ref=self._screenshot_ref(self.current_snapshot),
            failure_packet=failure_packet,
        )

        completed_count = len(self.completed_steps)
        if completed_count <= self._last_full_replan_progress_count:
            self._no_progress_full_replans += 1
        else:
            self._no_progress_full_replans = 1
        self._last_full_replan_progress_count = completed_count

        if self._no_progress_full_replans >= self._no_progress_full_replan_limit:
            self.phase = "blocked"
            self.step_phase = "idle"
            return [self._build_blocked_event("consecutive full replans made no progress")]

        self.plan = deepcopy(decision.get("new_plan") or {"goal": self.goal, "steps": []})
        self.plan["steps"] = self._uniquify_new_steps(self.plan.get("steps") or [], prefix_existing=False)
        self.plan_summary = self.plan.get("goal") or self.goal
        self.step_index = 0
        self._local_retry_count = 0
        self._checkpoint_confirmed = False

        if not self.plan.get("steps"):
            self.phase = "done"
            self.step_phase = "idle"
            return [self._build_done_event(self.plan_summary or "Guide completed")]

        self.phase = "running"
        return await self._locate_current_step(include_plan_ready=True)

    def _emit_selected_candidate(self, step: dict, candidates: list[dict], candidate_ids: list[str]) -> list[dict]:
        selected_id = candidate_ids[0] if candidate_ids else None
        selected = next((candidate for candidate in candidates if candidate.get("id") == selected_id), None)
        if selected is None:
            return self._build_guidance_events(step, {"status": "not_found", "targets": {}}, include_plan_ready=False)

        self.step_phase = "checkpoint_wait" if step.get("critical") else "guiding"
        transport_step = self._transport_step(step)
        return [
            self._build_plan_step_event(transport_step),
            {
                "protocol_version": "v1",
                "event": "guide.highlight",
                "step_id": transport_step["step_id"],
                "target": {
                    "relative_box": selected.get("bbox"),
                    "confidence": selected.get("confidence", 0.6),
                },
                "tooltip": step.get("instruction", transport_step["description"]),
                "require_manual_next": bool(step.get("critical", False)),
            },
        ]

    def _apply_target_patch(self, step: dict, decision: dict) -> None:
        if decision.get("target_patch"):
            step["target"] = deepcopy(decision["target_patch"])
        if decision.get("instruction_patch"):
            step["instruction"] = decision["instruction_patch"]
            step["title"] = decision["instruction_patch"]

    def _is_step_successful(self, step: dict, observation: dict) -> bool:
        criteria = [criterion.get("type") for criterion in step.get("success_criteria") or []]
        signals = observation.get("signals") or {}
        machine_criteria = [criterion for criterion in criteria if criterion != "user_confirmed"]

        if any(signals.get(criterion) for criterion in machine_criteria):
            return True

        if observation.get("status") == "ok":
            return True

        return bool(self._checkpoint_confirmed and "user_confirmed" in criteria)

    def _transport_step(self, step: dict) -> dict:
        return {
            "step_id": step["id"],
            "action": step.get("action_family") or self._infer_action(step),
            "description": step.get("instruction") or step.get("title") or step["id"],
            "reason": step.get("title") or "",
            "require_manual_next": bool(step.get("critical", False)),
        }

    def _infer_action(self, step: dict) -> str:
        action_family = step.get("action_family") or step.get("action")
        if action_family:
            return action_family

        target = step.get("target") or {}
        target_kind = target.get("kind")
        if target_kind == "source_target":
            return "drag"
        if target_kind == "region_only":
            return "observe"
        return "click"

    def _build_plan_ready_event(self) -> dict:
        return {
            "protocol_version": "v1",
            "event": "plan.ready",
            "summary": self.plan_summary or self.goal,
            "total_steps": len(self.plan.get("steps") or []),
            "current_step_index": self.step_index + 1,
            "steps": self.transport_plan_steps(),
        }

    def _build_plan_step_event(self, transport_step: dict) -> dict:
        return {
            "protocol_version": "v1",
            "event": "plan.step",
            "step_id": transport_step["step_id"],
            "total_steps": len(self.plan.get("steps") or []),
            "action": transport_step["action"],
            "description": transport_step["description"],
            "reason": transport_step["reason"],
        }

    def _build_done_event(self, summary: str) -> dict:
        return {
            "protocol_version": "v1",
            "event": "session.done",
            "summary": summary,
        }

    def _build_blocked_event(self, message: str) -> dict:
        return {
            "protocol_version": "v1",
            "event": "session.error",
            "code": "E_RUNTIME_BLOCKED",
            "message": message,
            "recoverable": False,
        }

    def _primary_box(self, locate_result: dict) -> list[float] | None:
        primary_target = self._primary_target(locate_result)
        if primary_target is None:
            return None
        return primary_target.get("bbox")

    def _primary_confidence(self, locate_result: dict) -> float:
        primary_target = self._primary_target(locate_result)
        if primary_target is None:
            return 0.6
        return primary_target.get("confidence", 0.6)

    def _primary_target(self, locate_result: dict) -> dict | None:
        targets = locate_result.get("targets") or {}
        for role in ("primary", "source", "destination"):
            if role in targets:
                return targets[role]
        return next(iter(targets.values()), None)

    def _failure_snapshot(self, step: dict, observation: dict) -> dict:
        context = self.current_snapshot.get("context") or {}
        return {
            "window_signature": {
                "process": context.get("process_name", ""),
                "title": context.get("window_title", ""),
            },
            "target_summary": deepcopy(step.get("target") or {}),
            "candidate_summary": self._flatten_candidates(observation),
        }

    def _flatten_candidates(self, observation: dict) -> list[dict]:
        candidate_sets = observation.get("candidate_sets") or {}
        flattened = []
        for role, candidates in candidate_sets.items():
            for candidate in candidates or []:
                current = deepcopy(candidate)
                current.setdefault("role", role)
                flattened.append(current)

        if flattened:
            return flattened

        targets = observation.get("targets") or {}
        for role, target in targets.items():
            current = deepcopy(target)
            current.setdefault("role", role)
            flattened.append(current)

        return flattened

    def _current_step_summary(self, step: dict) -> dict:
        return {
            "id": step.get("id"),
            "title": step.get("title"),
            "target_summary": deepcopy(step.get("target") or {}),
        }

    def _recent_progress_context(self) -> list[dict]:
        return [
            {
                "id": step.get("id"),
                "title": step.get("title"),
                "result": "done",
            }
            for step in self.completed_steps[-3:]
        ]

    def _screenshot_ref(self, snapshot: dict) -> str:
        return snapshot.get("image_base64", "")

    def _surface_context(self, snapshot: dict) -> dict:
        if snapshot.get("surface"):
            return deepcopy(snapshot["surface"])

        context = snapshot.get("context") or {}
        return {
            "kind": context.get("window_kind", "main"),
            "process_name": context.get("process_name", ""),
            "window_title": context.get("window_title", ""),
        }

    def _uniquify_new_steps(self, steps: list[dict], *, prefix_existing: bool = True) -> list[dict]:
        existing_ids = {step.get("id") for step in self.plan.get("steps") or []} if prefix_existing else set()
        normalized = []
        for index, step in enumerate(steps, start=1):
            current = deepcopy(step)
            base_id = current.get("id") or f"step_{index}"
            candidate_id = base_id
            suffix = 2
            while candidate_id in existing_ids:
                candidate_id = f"{base_id}__{suffix}"
                suffix += 1
            current["id"] = candidate_id
            existing_ids.add(candidate_id)
            normalized.append(current)
        return normalized
