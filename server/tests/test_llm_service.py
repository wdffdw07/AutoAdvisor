import unittest

from services.llm_service import adapt_agent_response


class AdaptAgentResponseTests(unittest.TestCase):
    def test_click_response_becomes_plan_and_highlight(self):
        events = adapt_agent_response(
            {"action": "click", "box": [10, 20, 30, 40], "tooltip": "Click here", "reason": "next"},
            step_id="s-001",
            total_steps=3,
        )

        self.assertEqual(events[0]["event"], "plan.step")
        self.assertEqual(events[1]["event"], "guide.highlight")
        self.assertFalse(events[1]["require_manual_next"])

    def test_complete_response_becomes_session_done(self):
        events = adapt_agent_response(
            {"action": "complete", "box": None, "tooltip": "Done", "reason": "finished"},
            step_id="s-003",
            total_steps=3,
        )

        self.assertEqual(events[-1]["event"], "session.done")


if __name__ == "__main__":
    unittest.main()
