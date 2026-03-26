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
    async def plan_steps(self, **_kwargs):
        return {
            "summary": "完整引导计划",
            "steps": [
                {"action": "click", "description": "打开特效面板", "reason": "进入特效工作区"},
                {"action": "input_text", "description": "搜索弹跳入场", "reason": "缩小候选范围"},
                {"action": "drag", "description": "拖到时间轴", "reason": "把特效应用到素材"},
            ],
        }

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

        self.assertEqual(len(websocket.sent), 3)
        self.assertIn('"event": "plan.ready"', websocket.sent[0])

    async def test_v1_session_complete_returns_session_done(self):
        websocket = FakeWebSocket(
            [
                (
                    '{"protocol_version":"v1","event":"session.start","trace_id":"t-1",'
                    '"session_id":"s-1","goal":"blur the image","context":{"process_name":"Photoshop.exe",'
                    '"window_title":"Photoshop","dpi_scale":1.0,"window_box":[100,50,1400,900]},'
                    '"image_base64":"abc123"}'
                ),
                (
                    '{"protocol_version":"v1","event":"session.complete","trace_id":"t-2",'
                    '"session_id":"s-1"}'
                ),
            ]
        )

        with mock.patch.object(main, "get_agent", return_value=FakeAgent()):
            await main.websocket_endpoint(websocket)

        self.assertGreaterEqual(len(websocket.sent), 4)
        self.assertIn('"event": "session.done"', websocket.sent[-1])


if __name__ == "__main__":
    unittest.main()
