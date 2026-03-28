import unittest

from api.ws_router import SessionState, build_session_error, handle_client_payload, normalize_client_message


class NormalizeClientMessageTests(unittest.TestCase):
    def test_v1_session_start_keeps_required_fields(self):
        payload = {
            "protocol_version": "v1",
            "event": "session.start",
            "trace_id": "t-1",
            "session_id": "s-1",
            "goal": "blur the image",
            "context": {
                "process_name": "Photoshop.exe",
                "window_title": "Photoshop",
                "dpi_scale": 1.0,
                "window_box": [100, 50, 1400, 900],
            },
            "image_base64": "abc123",
        }

        normalized = normalize_client_message(payload)

        self.assertEqual(normalized["event"], "session.start")
        self.assertEqual(normalized["goal"], "blur the image")
        self.assertEqual(normalized["context"]["window_box"], [100, 50, 1400, 900])

    def test_legacy_screenshot_maps_into_internal_start_shape(self):
        payload = {
            "type": "screenshot",
            "task": "blur the image",
            "data": "abc123",
            "windowRect": {"left": 100, "top": 50, "width": 1400, "height": 900},
        }

        normalized = normalize_client_message(payload)

        self.assertEqual(normalized["event"], "session.start")
        self.assertEqual(normalized["protocol_version"], "legacy")
        self.assertEqual(normalized["context"]["window_box"], [100, 50, 1400, 900])

    def test_missing_required_v1_fields_produces_bad_request_error(self):
        error = build_session_error("E_BAD_REQUEST", "missing context", recoverable=False)

        self.assertEqual(error["event"], "session.error")
        self.assertEqual(error["code"], "E_BAD_REQUEST")


class HandleClientPayloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_next_delegates_to_confirm_session(self):
        class FakeService:
            def __init__(self):
                self.confirm_calls = []

            async def confirm_session(self, session_state, payload):
                self.confirm_calls.append((session_state, payload))
                return [{"protocol_version": "v1", "event": "guide.wait_manual", "tooltip": "confirmed"}]

        service = FakeService()
        session_state = SessionState(
            session_id="s-1",
            goal="blur the image",
            protocol_version="v1",
            context={
                "process_name": "Photoshop.exe",
                "window_title": "Photoshop",
                "dpi_scale": 1.0,
                "window_box": [100, 50, 1400, 900],
            },
        )
        payload = {
            "protocol_version": "v1",
            "event": "user.next",
            "trace_id": "t-2",
            "session_id": "s-1",
        }

        new_state, events = await handle_client_payload(payload, session_state, service)

        self.assertIs(new_state, session_state)
        self.assertEqual(len(service.confirm_calls), 1)
        self.assertEqual(events[0]["event"], "guide.wait_manual")
        self.assertEqual(events[0]["trace_id"], "t-2")
        self.assertEqual(events[0]["session_id"], "s-1")


if __name__ == "__main__":
    unittest.main()
