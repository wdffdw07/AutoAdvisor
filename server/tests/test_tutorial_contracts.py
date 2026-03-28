import unittest

from services.tutorial_contracts import (
    is_visualizable_step,
    validate_plan,
    validate_step,
)


VALID_STEP = {
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


class TutorialContractTests(unittest.TestCase):
    def test_validate_step_preserves_a_visualizable_step(self):
        normalized = validate_step(VALID_STEP)

        self.assertEqual(normalized["id"], "step_1")
        self.assertFalse(normalized["critical"])
        self.assertEqual(normalized["target"]["kind"], "single")
        self.assertEqual(normalized["window_expectation"]["relation"], "stay_on_current")

    def test_validate_step_normalizes_optional_maps(self):
        step = dict(VALID_STEP)
        step.pop("critical")
        step.pop("recovery_hints")

        normalized = validate_step(step)

        self.assertFalse(normalized["critical"])
        self.assertEqual(normalized["recovery_hints"], {})

    def test_validate_step_rejects_unknown_target_kind(self):
        step = dict(VALID_STEP)
        step["target"] = {"kind": "freeform", "hints": {}}

        with self.assertRaisesRegex(ValueError, "target.kind"):
            validate_step(step)

    def test_validate_step_rejects_missing_instruction(self):
        step = dict(VALID_STEP)
        step.pop("instruction")

        with self.assertRaisesRegex(ValueError, "instruction"):
            validate_step(step)

    def test_validate_step_rejects_missing_success_criteria(self):
        step = dict(VALID_STEP)
        step.pop("success_criteria")

        with self.assertRaisesRegex(ValueError, "success_criteria"):
            validate_step(step)

    def test_validate_step_rejects_missing_window_expectation(self):
        step = dict(VALID_STEP)
        step.pop("window_expectation")

        with self.assertRaisesRegex(ValueError, "window_expectation"):
            validate_step(step)

    def test_is_visualizable_step_rejects_empty_region_only_target(self):
        step = dict(VALID_STEP)
        step["target"] = {"kind": "region_only", "hints": {}}

        self.assertFalse(is_visualizable_step(step))

    def test_validate_step_rejects_non_visualizable_target(self):
        step = dict(VALID_STEP)
        step["target"] = {"kind": "region_only", "hints": {}}

        with self.assertRaisesRegex(ValueError, "visual"):
            validate_step(step)

    def test_validate_plan_normalizes_all_steps(self):
        plan = {
            "goal": "Configure application settings",
            "steps": [
                VALID_STEP,
                {
                    **VALID_STEP,
                    "id": "step_2",
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
                },
            ],
        }

        normalized = validate_plan(plan)

        self.assertEqual(normalized["goal"], "Configure application settings")
        self.assertEqual(len(normalized["steps"]), 2)
        self.assertEqual(normalized["steps"][1]["id"], "step_2")

    def test_validate_plan_rejects_unknown_success_criteria_type(self):
        plan = {
            "goal": "Configure application settings",
            "steps": [
                {
                    **VALID_STEP,
                    "success_criteria": [{"type": "mystery_signal"}],
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "success_criteria"):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
