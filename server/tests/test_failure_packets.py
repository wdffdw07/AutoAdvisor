import unittest

from services.failure_packets import (
    append_recovery_action,
    begin_failure_episode,
    build_failure_packet,
)


class FailurePacketTests(unittest.TestCase):
    def test_begin_failure_episode_captures_snapshot_fields(self):
        episode = begin_failure_episode(
            step_id="step_3",
            failure_type="grounding_failed",
            snapshot={
                "window_signature": {"process": "ExampleApp.exe", "title": "Settings"},
                "target_summary": {"role": "button", "text": ["Save"]},
                "candidate_summary": [
                    {
                        "id": "cand_1",
                        "label": "Save",
                        "location": "bottom-right",
                        "bbox": [0.75, 0.88, 0.08, 0.05],
                        "cluster_id": "dialog_actions",
                        "order_in_cluster": 2,
                        "cluster_count": 3,
                    }
                ],
            },
        )

        self.assertEqual(episode["step_id"], "step_3")
        self.assertEqual(episode["failure_type"], "grounding_failed")
        self.assertEqual(episode["window_signature"]["process"], "ExampleApp.exe")
        self.assertEqual(episode["candidate_summary"][0]["cluster_id"], "dialog_actions")

    def test_append_recovery_action_tracks_attempt_history(self):
        episode = begin_failure_episode("step_3", "grounding_failed", {})

        append_recovery_action(episode, "recapture", "still_not_found")
        append_recovery_action(episode, "uia_retry", "still_not_found")

        self.assertEqual(len(episode["recovery_actions"]), 2)
        self.assertEqual(episode["attempt_count"], 2)
        self.assertEqual(episode["recovery_actions"][1]["action"], "uia_retry")

    def test_build_failure_packet_merges_repeated_failures_on_the_same_step(self):
        first = begin_failure_episode(
            "step_4",
            "grounding_failed",
            {
                "window_signature": {"process": "ExampleApp.exe", "title": "Export"},
                "candidate_summary": [{"id": "cand_1", "label": "Save", "location": "bottom-right"}],
            },
        )
        append_recovery_action(first, "recapture", "still_not_found")

        second = begin_failure_episode(
            "step_4",
            "grounding_failed",
            {
                "window_signature": {"process": "ExampleApp.exe", "title": "Export"},
                "candidate_summary": [{"id": "cand_1", "label": "Save", "location": "bottom-right"}],
            },
        )
        append_recovery_action(second, "ocr_cv_retry", "still_not_found")

        packet = build_failure_packet(
            current_step={"id": "step_4", "title": "Choose save location"},
            episodes=[first, second],
            recent_progress=[{"step_id": "step_2", "result": "done"}],
        )

        self.assertEqual(len(packet["recent_failure_episodes"]), 1)
        self.assertEqual(packet["recent_failure_episodes"][0]["attempt_count"], 2)
        self.assertEqual(packet["recent_failure_episodes"][0]["recovery_actions"][1]["action"], "ocr_cv_retry")

    def test_build_failure_packet_keeps_the_current_step_plus_three_recent_progress_items(self):
        packet = build_failure_packet(
            current_step={"id": "step_5", "title": "Confirm export"},
            episodes=[],
            recent_progress=[
                {"step_id": "step_1", "result": "done"},
                {"step_id": "step_2", "result": "done"},
                {"step_id": "step_3", "result": "done"},
                {"step_id": "step_4", "result": "done"},
            ],
        )

        self.assertEqual(packet["current_step"]["id"], "step_5")
        self.assertEqual(len(packet["recent_progress_context"]), 3)
        self.assertEqual(packet["recent_progress_context"][0]["step_id"], "step_2")
        self.assertEqual(packet["recent_progress_context"][2]["step_id"], "step_4")

    def test_build_failure_packet_preserves_candidate_geometry_and_semantics(self):
        episode = begin_failure_episode(
            "step_6",
            "grounding_failed",
            {
                "candidate_summary": [
                    {
                        "id": "cand_2",
                        "label": "Export",
                        "location": "top-right",
                        "confidence_band": "high",
                        "bbox": [0.82, 0.06, 0.1, 0.05],
                        "center": [0.87, 0.085],
                        "cluster_id": "title_actions",
                        "order_in_cluster": 1,
                        "cluster_count": 2,
                    }
                ]
            },
        )
        append_recovery_action(episode, "uia_retry", "still_not_found")

        packet = build_failure_packet(
            current_step={"id": "step_6", "title": "Open export"},
            episodes=[episode],
            recent_progress=[],
        )

        candidate = packet["recent_failure_episodes"][0]["candidate_summary"][0]
        self.assertEqual(candidate["label"], "Export")
        self.assertEqual(candidate["location"], "top-right")
        self.assertEqual(candidate["bbox"], [0.82, 0.06, 0.1, 0.05])
        self.assertEqual(candidate["order_in_cluster"], 1)


if __name__ == "__main__":
    unittest.main()
