import unittest
from copy import deepcopy

from services.tutorial_runtime import TutorialRuntime


class FakePlanner:
    def __init__(self, initial_plan, step_retarget_results=None, partial_replan_results=None, full_replan_results=None):
        self.initial_plan_result = deepcopy(initial_plan)
        self.step_retarget_results = list(step_retarget_results or [])
        self.partial_replan_results = list(partial_replan_results or [])
        self.full_replan_results = list(full_replan_results or [])
        self.initial_plan_calls = []
        self.step_retarget_calls = []
        self.partial_replan_calls = []
        self.full_replan_calls = []

    async def initial_plan(self, goal, screenshot_ref, surface_context):
        self.initial_plan_calls.append((goal, screenshot_ref, surface_context))
        return deepcopy(self.initial_plan_result)

    async def step_retarget(self, current_step, screenshot_ref, candidates, failure_packet):
        self.step_retarget_calls.append((deepcopy(current_step), screenshot_ref, deepcopy(candidates), deepcopy(failure_packet)))
        result = self.step_retarget_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)

    async def partial_replan(self, goal, completed_steps, failed_step, screenshot_ref, failure_packet):
        self.partial_replan_calls.append((goal, deepcopy(completed_steps), deepcopy(failed_step), screenshot_ref, deepcopy(failure_packet)))
        result = self.partial_replan_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)

    async def full_replan(self, goal, trusted_history, screenshot_ref, failure_packet):
        self.full_replan_calls.append((goal, deepcopy(trusted_history), screenshot_ref, deepcopy(failure_packet)))
        result = self.full_replan_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)


class FakeGrounder:
    def __init__(self, locate_results=None, observe_results=None):
        self.locate_results = list(locate_results or [])
        self.observe_results = list(observe_results or [])
        self.locate_calls = []
        self.observe_calls = []

    def locate(self, step, snapshot):
        self.locate_calls.append((deepcopy(step), deepcopy(snapshot)))
        return deepcopy(self.locate_results.pop(0))

    def observe(self, step, snapshot):
        self.observe_calls.append((deepcopy(step), deepcopy(snapshot)))
        return deepcopy(self.observe_results.pop(0))


class TutorialRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def _snapshot(self, image_ref="img-1", title="Example App"):
        return {
            "image_base64": image_ref,
            "context": {
                "process_name": "ExampleApp.exe",
                "window_title": title,
                "dpi_scale": 1.0,
                "window_box": [100, 50, 1280, 800],
            },
            "surface": {
                "kind": "main",
                "process_name": "ExampleApp.exe",
                "window_title": title,
            },
        }

    def _step(self, step_id, instruction, *, critical=False, target_kind="single", retry_budget=1):
        target = {
            "kind": target_kind,
            "hints": {
                "role": "button",
                "text": [instruction],
                "region": "top-right",
            },
        }
        if target_kind == "source_target":
            target = {
                "kind": "source_target",
                "source": {"role": "list_item", "text": [instruction]},
                "destination": {"role": "drop_region", "region": "canvas"},
            }

        return {
            "id": step_id,
            "title": instruction,
            "instruction": instruction,
            "critical": critical,
            "target": target,
            "success_criteria": [{"type": "element_appeared"}],
            "recovery_hints": {"retry_budget": retry_budget},
            "window_expectation": {"relation": "stay_on_current"},
        }

    def _plan(self, *steps):
        return {"goal": "complete the tutorial", "steps": list(steps)}

    def _ok_target(self, label):
        return {
            "status": "ok",
            "targets": {
                "primary": {
                    "label": label,
                    "bbox": [0.8, 0.05, 0.1, 0.06],
                    "confidence": 0.9,
                }
            },
        }

    def _ok_observation(self):
        return {"status": "ok", "signals": {"element_appeared": True}}

    def _not_found(self, candidate_label="Maybe"):
        return {
            "status": "not_found",
            "targets": {},
            "candidate_sets": {
                "primary": [
                    {
                        "id": "cand-1",
                        "label": candidate_label,
                        "bbox": [0.78, 0.08, 0.11, 0.05],
                        "confidence": 0.62,
                    }
                ]
            },
        }

    async def test_start_generates_plan_and_guides_first_step(self):
        planner = FakePlanner(self._plan(self._step("step_1", "Open settings")))
        grounder = FakeGrounder(locate_results=[self._ok_target("Open settings")])
        runtime = TutorialRuntime(planner=planner, grounder=grounder)

        events = await runtime.start("open settings", self._snapshot())

        self.assertEqual(events[0]["event"], "plan.ready")
        self.assertEqual(events[1]["event"], "plan.step")
        self.assertEqual(events[2]["event"], "guide.highlight")
        self.assertEqual(runtime.phase, "running")
        self.assertEqual(runtime.step_phase, "guiding")
        self.assertEqual(runtime.step_index, 0)

    async def test_observe_advances_to_next_step_and_enters_checkpoint_wait_for_critical_steps(self):
        plan = self._plan(
            self._step("step_1", "Open settings"),
            self._step("step_2", "Confirm export", critical=True),
        )
        planner = FakePlanner(plan)
        grounder = FakeGrounder(
            locate_results=[self._ok_target("Open settings"), self._ok_target("Confirm export")],
            observe_results=[self._ok_observation()],
        )
        runtime = TutorialRuntime(planner=planner, grounder=grounder)

        await runtime.start("export project", self._snapshot())
        events = await runtime.observe(self._snapshot(image_ref="img-2", title="Export dialog"))

        self.assertEqual(runtime.step_index, 1)
        self.assertEqual(runtime.step_phase, "checkpoint_wait")
        self.assertEqual(events[0]["event"], "plan.step")
        self.assertEqual(events[1]["event"], "guide.highlight")
        self.assertTrue(events[1]["require_manual_next"])

    async def test_confirm_checkpoint_moves_runtime_into_observing_state(self):
        plan = self._plan(self._step("step_1", "Confirm export", critical=True))
        planner = FakePlanner(plan)
        grounder = FakeGrounder(locate_results=[self._ok_target("Confirm export")])
        runtime = TutorialRuntime(planner=planner, grounder=grounder)

        await runtime.start("export project", self._snapshot())
        events = await runtime.confirm_checkpoint()

        self.assertEqual(events, [])
        self.assertEqual(runtime.step_phase, "observing")

    async def test_partial_replan_replaces_only_remaining_steps_and_keeps_completed_steps(self):
        step_1 = self._step("step_1", "Open settings")
        step_2 = self._step("step_2", "Choose preset", retry_budget=1)
        replacement = self._step("step_2r", "Choose export preset")
        planner = FakePlanner(
            self._plan(step_1, step_2),
            step_retarget_results=[
                {
                    "decision": "request_partial_replan",
                    "step_id": "step_2",
                    "reason": "current target is no longer valid",
                }
            ],
            partial_replan_results=[
                {
                    "decision": "replace_remaining_steps",
                    "start_from_failed_step": "step_2",
                    "new_steps": [replacement],
                }
            ],
        )
        grounder = FakeGrounder(
            locate_results=[
                self._ok_target("Open settings"),
                self._ok_target("Choose preset"),
                self._not_found("Preset"),
                self._ok_target("Choose export preset"),
            ],
            observe_results=[self._ok_observation(), self._not_found("Preset")],
        )
        runtime = TutorialRuntime(planner=planner, grounder=grounder)

        await runtime.start("export project", self._snapshot())
        await runtime.observe(self._snapshot(image_ref="img-2"))
        events = await runtime.observe(self._snapshot(image_ref="img-3", title="Export settings"))

        self.assertEqual(planner.step_retarget_calls[0][0]["id"], "step_2")
        self.assertEqual(len(planner.partial_replan_calls[0][1]), 1)
        self.assertEqual(runtime.completed_steps[0]["id"], "step_1")
        self.assertEqual([step["id"] for step in runtime.plan["steps"]], ["step_1", "step_2r"])
        self.assertEqual(runtime.step_index, 1)
        self.assertEqual(events[0]["event"], "plan.ready")
        self.assertEqual(events[1]["step_id"], "step_2r")

    async def test_consecutive_no_progress_full_replans_block_the_runtime(self):
        step_1 = self._step("step_1", "Open settings", retry_budget=0)
        planner = FakePlanner(
            self._plan(step_1),
            step_retarget_results=[
                {
                    "decision": "request_partial_replan",
                    "step_id": "step_1",
                    "reason": "missing target",
                },
                {
                    "decision": "request_partial_replan",
                    "step_id": "step_1f1",
                    "reason": "still missing target",
                },
            ],
            partial_replan_results=[RuntimeError("cannot patch remaining steps"), RuntimeError("cannot patch remaining steps")],
            full_replan_results=[
                {"decision": "replace_entire_active_plan", "new_plan": self._plan(self._step("step_1f1", "Open settings again", retry_budget=0))},
                {"decision": "replace_entire_active_plan", "new_plan": self._plan(self._step("step_1f2", "Open settings once more", retry_budget=0))},
            ],
        )
        grounder = FakeGrounder(
            locate_results=[
                self._ok_target("Open settings"),
                self._ok_target("Open settings again"),
            ],
            observe_results=[self._not_found("Settings"), self._not_found("Settings")],
        )
        runtime = TutorialRuntime(planner=planner, grounder=grounder)

        await runtime.start("open settings", self._snapshot())
        first_events = await runtime.observe(self._snapshot(image_ref="img-2"))
        second_events = await runtime.observe(self._snapshot(image_ref="img-3"))

        self.assertEqual(first_events[0]["event"], "plan.ready")
        self.assertEqual(len(planner.full_replan_calls), 2)
        self.assertEqual(runtime.phase, "blocked")
        self.assertEqual(second_events[-1]["event"], "session.error")
        self.assertEqual(second_events[-1]["code"], "E_RUNTIME_BLOCKED")


if __name__ == "__main__":
    unittest.main()
