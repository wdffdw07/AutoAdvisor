import unittest

from api.ws_router import SessionState
from services.llm_service import LLMSessionService, adapt_agent_response


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


class FakeAgent:
    def __init__(self):
        self.plan_calls = 0
        self.analysis_calls = []

    async def plan_steps(self, **_kwargs):
        self.plan_calls += 1
        return {
            "summary": "完整引导计划",
            "steps": [
                {"action": "click", "description": "打开特效面板", "reason": "进入特效工作区"},
                {"action": "input_text", "description": "搜索弹跳入场", "reason": "缩小候选范围"},
                {"action": "drag", "description": "拖到时间轴", "reason": "把特效应用到素材"},
                {"action": "click", "description": "确认应用", "reason": "关闭弹窗并完成"},
            ],
        }

    async def analyze_screenshot(self, **kwargs):
        self.analysis_calls.append(kwargs)
        return {
            "action": "click",
            "box": [10, 20, 30, 40],
            "tooltip": "定位到当前步骤",
            "reason": "当前界面可执行该步骤",
        }


class SessionServicePlanTests(unittest.IsolatedAsyncioTestCase):
    def _session_state(self):
        return SessionState(
            session_id="s-1",
            goal="add effect",
            protocol_version="v1",
            context={
                "process_name": "JianyingPro.exe",
                "window_title": "Jianying",
                "dpi_scale": 1.0,
                "window_box": [100, 50, 1400, 900],
            },
        )

    async def test_start_session_emits_plan_ready_with_actual_total_steps(self):
        agent = FakeAgent()
        service = LLMSessionService(lambda: agent)
        session_state = self._session_state()

        events = await service.start_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "abc123",
            },
        )

        self.assertEqual(events[0]["event"], "plan.ready")
        self.assertEqual(events[0]["total_steps"], 4)
        self.assertEqual(len(events[0]["steps"]), 4)
        self.assertEqual(events[1]["event"], "plan.step")
        self.assertEqual(events[1]["description"], "打开特效面板")
        self.assertEqual(events[2]["event"], "guide.highlight")
        self.assertEqual(agent.plan_calls, 1)
        self.assertEqual(len(agent.analysis_calls), 1)

    async def test_advance_session_uses_cached_plan_steps(self):
        agent = FakeAgent()
        service = LLMSessionService(lambda: agent)
        session_state = self._session_state()

        await service.start_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "abc123",
            },
        )
        events = await service.advance_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "def456",
            },
        )

        self.assertEqual(events[0]["event"], "plan.step")
        self.assertEqual(events[0]["step_id"], "s-002")
        self.assertEqual(events[0]["description"], "搜索弹跳入场")
        self.assertEqual(agent.plan_calls, 1)

    async def test_complete_session_emits_session_done(self):
        agent = FakeAgent()
        service = LLMSessionService(lambda: agent)
        session_state = self._session_state()

        await service.start_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "abc123",
            },
        )

        events = await service.complete_session(session_state, {"goal": "add effect"})

        self.assertEqual(events[-1]["event"], "session.done")
        self.assertTrue(session_state.done)

    async def test_advance_session_extends_the_plan_when_more_steps_are_needed(self):
        class ExtendingAgent:
            def __init__(self):
                self.plan_calls = 0

            async def plan_steps(self, **_kwargs):
                self.plan_calls += 1
                if self.plan_calls == 1:
                    return {
                        "summary": "初始计划",
                        "steps": [
                            {"action": "click", "description": "打开特效面板", "reason": "进入特效面板"},
                            {"action": "input_text", "description": "搜索弹跳入场", "reason": "缩小范围"},
                            {"action": "drag", "description": "拖动到时间轴", "reason": "应用特效"},
                        ],
                    }

                return {
                    "summary": "补充计划",
                    "steps": [
                        {"action": "click", "description": "确认应用", "reason": "完成特效添加"},
                        {"action": "complete", "description": "检查结果", "reason": "确认任务完成"},
                    ],
                }

            async def analyze_screenshot(self, **_kwargs):
                return {
                    "action": "click",
                    "box": [10, 20, 30, 40],
                    "tooltip": "定位到当前步骤",
                    "reason": "当前界面可执行该步骤",
                }

        agent = ExtendingAgent()
        service = LLMSessionService(lambda: agent)
        session_state = self._session_state()

        await service.start_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "abc123",
            },
        )
        await service.advance_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "def456",
            },
        )
        await service.advance_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "ghi789",
            },
        )

        events = await service.advance_session(
            session_state,
            {
                "goal": "add effect",
                "context": session_state.context,
                "image_base64": "jkl012",
            },
        )

        self.assertEqual(events[0]["event"], "plan.ready")
        self.assertEqual(events[0]["total_steps"], 5)
        self.assertEqual(events[1]["event"], "plan.step")
        self.assertEqual(events[1]["step_id"], "s-004")
        self.assertEqual(events[1]["description"], "确认应用")
        self.assertFalse(session_state.done)
        self.assertEqual(agent.plan_calls, 2)


if __name__ == "__main__":
    unittest.main()
