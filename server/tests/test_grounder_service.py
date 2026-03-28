import unittest

from services.grounders.grounder_service import GrounderService


class FakeBackend:
    def __init__(self, locate_result, observe_result=None):
        self.locate_result = locate_result
        self.observe_result = observe_result if observe_result is not None else locate_result
        self.locate_calls = []
        self.observe_calls = []

    def locate(self, step, surface_snapshot):
        self.locate_calls.append((step, surface_snapshot))
        return self.locate_result

    def observe(self, step, surface_snapshot):
        self.observe_calls.append((step, surface_snapshot))
        return self.observe_result


class GrounderServiceTests(unittest.TestCase):
    def setUp(self):
        self.single_step = {
            "id": "step_1",
            "target": {
                "kind": "single",
                "hints": {"role": "button", "text": ["Settings"], "region": "top-right"},
            },
        }
        self.source_target_step = {
            "id": "step_2",
            "target": {
                "kind": "source_target",
                "source": {"role": "list_item", "text": ["Vintage"]},
                "destination": {"role": "drop_region", "region": "timeline"},
            },
        }
        self.surface_snapshot = {"kind": "main", "process_name": "ExampleApp.exe"}

    def test_uia_runs_first_and_short_circuits_on_match(self):
        uia = FakeBackend(
            {
                "status": "ok",
                "targets": {
                    "primary": {
                        "label": "Settings",
                        "bbox": [0.81, 0.06, 0.09, 0.05],
                        "confidence": 0.91,
                    }
                },
            }
        )
        vision = FakeBackend({"status": "not_found", "targets": {}})
        service = GrounderService(uia_backend=uia, vision_backend=vision)

        result = service.locate(self.single_step, self.surface_snapshot)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "uia")
        self.assertEqual(result["targets"]["primary"]["backend"], "uia")
        self.assertEqual(len(uia.locate_calls), 1)
        self.assertEqual(len(vision.locate_calls), 0)

    def test_vision_fallback_runs_only_after_uia_miss(self):
        uia = FakeBackend({"status": "not_found", "targets": {}})
        vision = FakeBackend(
            {
                "status": "ok",
                "targets": {
                    "primary": {
                        "label": "Settings",
                        "bbox": [0.8, 0.05, 0.1, 0.06],
                        "confidence": 0.73,
                    }
                },
            }
        )
        service = GrounderService(uia_backend=uia, vision_backend=vision)

        result = service.locate(self.single_step, self.surface_snapshot)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "vision")
        self.assertEqual(result["targets"]["primary"]["backend"], "vision")
        self.assertEqual(len(uia.locate_calls), 1)
        self.assertEqual(len(vision.locate_calls), 1)

    def test_ambiguous_results_are_returned_as_candidate_sets(self):
        uia = FakeBackend(
            {
                "status": "ambiguous",
                "candidate_sets": {
                    "primary": [
                        {"id": "cand_1", "label": "Settings", "bbox": [0.8, 0.05, 0.1, 0.05], "confidence": 0.81},
                        {"id": "cand_2", "label": "Options", "bbox": [0.7, 0.05, 0.1, 0.05], "confidence": 0.74},
                    ]
                },
            }
        )
        vision = FakeBackend({"status": "not_found", "targets": {}})
        service = GrounderService(uia_backend=uia, vision_backend=vision)

        result = service.locate(self.single_step, self.surface_snapshot)

        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["backend"], "uia")
        self.assertEqual(len(result["candidate_sets"]["primary"]), 2)
        self.assertEqual(result["candidate_sets"]["primary"][0]["backend"], "uia")
        self.assertEqual(len(vision.locate_calls), 0)

    def test_source_target_steps_keep_both_roles(self):
        uia = FakeBackend({"status": "not_found", "targets": {}})
        vision = FakeBackend(
            {
                "status": "ok",
                "targets": {
                    "source": {
                        "label": "Vintage",
                        "bbox": [0.12, 0.24, 0.18, 0.08],
                        "confidence": 0.8,
                    },
                    "destination": {
                        "label": "Timeline",
                        "bbox": [0.25, 0.74, 0.5, 0.12],
                        "confidence": 0.76,
                    },
                },
            }
        )
        service = GrounderService(uia_backend=uia, vision_backend=vision)

        result = service.locate(self.source_target_step, self.surface_snapshot)

        self.assertEqual(result["status"], "ok")
        self.assertIn("source", result["targets"])
        self.assertIn("destination", result["targets"])
        self.assertEqual(result["targets"]["source"]["backend"], "vision")
        self.assertEqual(result["targets"]["destination"]["backend"], "vision")


if __name__ == "__main__":
    unittest.main()
