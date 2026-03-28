import unittest

from services.planner_service import PlannerService


VALID_CONTRACT_STEP = {
    "id": "step_1",
    "title": "Open settings",
    "instruction": "Click here to open settings",
    "critical": False,
    "target": {
        "kind": "single",
        "hints": {
            "role": "button",
            "text": ["Settings", "Preferences"],
            "region": "top-right",
        },
    },
    "success_criteria": [{"type": "element_appeared", "target": "settings_menu"}],
    "recovery_hints": {"retry_budget": 2},
    "window_expectation": {"relation": "stay_on_current"},
}


class LegacyPlanningAgent:
    async def plan_steps(self, **_kwargs):
        return {
            "summary": "Open the settings menu and confirm the dialog",
            "steps": [
                {
                    "action": "click",
                    "description": "Open settings",
                    "reason": "Navigate into the settings flow",
                    "require_manual_next": False,
                },
                {
                    "action": "click",
                    "description": "Confirm the dialog",
                    "reason": "Apply the current settings",
                    "require_manual_next": True,
                },
            ],
        }


class StructuredPlanningAgent:
    def __init__(self, invalid_step=None):
        self.invalid_step = invalid_step

    async def build_initial_tutorial_plan(self, **_kwargs):
        steps = [VALID_CONTRACT_STEP]
        if self.invalid_step is not None:
            steps = [self.invalid_step]
        return {
            "goal": "Configure application settings",
            "steps": steps,
        }

    async def retarget_tutorial_step(self, **_kwargs):
        return {
            "decision": "select_candidate",
            "step_id": "step_1",
            "candidate_ids": ["cand_1"],
        }

    async def replan_remaining_steps(self, **_kwargs):
        return {
            "decision": "replace_remaining_steps",
            "start_from_failed_step": "step_2",
            "new_steps": [
                {
                    **VALID_CONTRACT_STEP,
                    "id": "step_2r",
                    "title": "Confirm the dialog",
                    "instruction": "Click here to confirm the dialog",
                    "target": {
                        "kind": "single",
                        "hints": {
                            "role": "button",
                            "text": ["OK", "Confirm"],
                            "region": "bottom-right",
                        },
                    },
                    "success_criteria": [{"type": "element_disappeared", "target": "settings_dialog"}],
                }
            ],
        }

    async def replan_from_current_state(self, **_kwargs):
        return {
            "decision": "replace_entire_active_plan",
            "new_plan": {
                "goal": "Configure application settings",
                "steps": [VALID_CONTRACT_STEP],
            },
        }


class InvalidRetargetAgent(StructuredPlanningAgent):
    async def retarget_tutorial_step(self, **_kwargs):
        return {
            "decision": "refine_target",
            "step_id": "step_1",
            "target_patch": {"kind": "freeform", "hints": {}},
            "instruction_patch": "Click here to open settings",
        }


class PlannerServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_plan_adapts_legacy_plan_steps_into_contract_steps(self):
        service = PlannerService(lambda: LegacyPlanningAgent())

        plan = await service.initial_plan(
            goal="Configure application settings",
            screenshot_ref="abc123",
            surface_context={"kind": "main", "process_name": "ExampleApp.exe"},
        )

        self.assertEqual(plan["goal"], "Configure application settings")
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["id"], "step_1")
        self.assertEqual(plan["steps"][0]["target"]["kind"], "region_only")
        self.assertEqual(plan["steps"][1]["window_expectation"]["relation"], "stay_on_current")

    async def test_initial_plan_rejects_invalid_structured_steps(self):
        invalid_step = {
            **VALID_CONTRACT_STEP,
            "target": {"kind": "region_only", "hints": {}},
        }
        service = PlannerService(lambda: StructuredPlanningAgent(invalid_step=invalid_step))

        with self.assertRaisesRegex(ValueError, "visual"):
            await service.initial_plan(
                goal="Configure application settings",
                screenshot_ref="abc123",
                surface_context={"kind": "main", "process_name": "ExampleApp.exe"},
            )

    async def test_step_retarget_accepts_candidate_selection(self):
        service = PlannerService(lambda: StructuredPlanningAgent())

        decision = await service.step_retarget(
            current_step=VALID_CONTRACT_STEP,
            screenshot_ref="abc123",
            candidates=[{"id": "cand_1", "label": "Settings"}],
            failure_packet={"current_step": {"id": "step_1"}},
        )

        self.assertEqual(decision["decision"], "select_candidate")
        self.assertEqual(decision["candidate_ids"], ["cand_1"])

    async def test_step_retarget_rejects_invalid_target_patch(self):
        service = PlannerService(lambda: InvalidRetargetAgent())

        with self.assertRaisesRegex(ValueError, "target.kind"):
            await service.step_retarget(
                current_step=VALID_CONTRACT_STEP,
                screenshot_ref="abc123",
                candidates=[{"id": "cand_1", "label": "Settings"}],
                failure_packet={"current_step": {"id": "step_1"}},
            )

    async def test_partial_replan_validates_replacement_steps(self):
        service = PlannerService(lambda: StructuredPlanningAgent())

        decision = await service.partial_replan(
            goal="Configure application settings",
            completed_steps=[VALID_CONTRACT_STEP],
            failed_step={**VALID_CONTRACT_STEP, "id": "step_2"},
            screenshot_ref="abc123",
            failure_packet={"current_step": {"id": "step_2"}},
        )

        self.assertEqual(decision["decision"], "replace_remaining_steps")
        self.assertEqual(decision["new_steps"][0]["id"], "step_2r")

    async def test_full_replan_validates_the_new_plan(self):
        service = PlannerService(lambda: StructuredPlanningAgent())

        decision = await service.full_replan(
            goal="Configure application settings",
            trusted_history=[{"id": "step_1", "result": "done"}],
            screenshot_ref="abc123",
            failure_packet={"recent_failure_episodes": []},
        )

        self.assertEqual(decision["decision"], "replace_entire_active_plan")
        self.assertEqual(decision["new_plan"]["steps"][0]["id"], "step_1")


if __name__ == "__main__":
    unittest.main()
