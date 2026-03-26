import unittest
from unittest import mock

from fastapi import WebSocketDisconnect

import main


class FakeWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if self._messages:
            return self._messages.pop(0)
        raise WebSocketDisconnect()

    async def send_text(self, payload):
        self.sent.append(payload)


class FakeAgent:
    async def analyze_screenshot(self, **_kwargs):
        return {
            "action": "click",
            "box": [10, 20, 30, 40],
            "tooltip": "Click here",
            "reason": "next",
        }


class WebSocketSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_screenshot_still_returns_legacy_action_shape(self):
        websocket = FakeWebSocket(
            [
                (
                    '{"type":"screenshot","task":"blur the image","data":"abc123",'
                    '"windowRect":{"left":100,"top":50,"width":1400,"height":900}}'
                )
            ]
        )

        with mock.patch.object(main, "get_agent", return_value=FakeAgent()):
            await main.websocket_endpoint(websocket)

        self.assertEqual(len(websocket.sent), 1)
        self.assertIn('"action": "click"', websocket.sent[0])

    async def test_v1_session_start_returns_plan_and_guide(self):
        websocket = FakeWebSocket(
            [
                (
                    '{"protocol_version":"v1","event":"session.start","trace_id":"t-1",'
                    '"session_id":"s-1","goal":"blur the image","context":{"process_name":"Photoshop.exe",'
                    '"window_title":"Photoshop","dpi_scale":1.0,"window_box":[100,50,1400,900]},'
                    '"image_base64":"abc123"}'
                )
            ]
        )

        with mock.patch.object(main, "get_agent", return_value=FakeAgent()):
            await main.websocket_endpoint(websocket)

        self.assertEqual(len(websocket.sent), 2)


if __name__ == "__main__":
    unittest.main()
