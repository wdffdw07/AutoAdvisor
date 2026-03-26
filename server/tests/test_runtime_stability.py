import io
import os
import runpy
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def strict_gbk_stdout():
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="gbk", errors="strict", newline="\n")
    try:
        with mock.patch("sys.stdout", stdout):
            yield stdout
            stdout.flush()
    finally:
        stdout.close()


class RuntimeStabilityTests(unittest.TestCase):
    def test_requirements_explicitly_include_sniffio(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        normalized = [line.strip().lower() for line in requirements if line.strip()]
        self.assertTrue(
            any(line.startswith("sniffio") for line in normalized),
            "requirements.txt must explicitly include sniffio for reproducible uv installs.",
        )

    def test_main_entry_logging_is_gbk_safe(self):
        with strict_gbk_stdout():
            with mock.patch("uvicorn.run") as uvicorn_run:
                with mock.patch.dict(
                    os.environ,
                    {"GLM_API_KEY": "", "OPENAI_API_KEY": "", "LLM_MODEL": "glm-4-flash"},
                    clear=False,
                ):
                    runpy.run_path(str(ROOT / "main.py"), run_name="__main__")

        uvicorn_run.assert_called_once()

    def test_llm_agent_initialization_logging_is_gbk_safe(self):
        sys.path.insert(0, str(ROOT))
        try:
            import llm_agent

            with mock.patch.dict(os.environ, {"LLM_MODEL": "glm-4-flash"}, clear=False):
                with strict_gbk_stdout():
                    with mock.patch.object(llm_agent, "ZhipuAI", return_value=object()):
                        with mock.patch.object(
                            llm_agent.JianyingAgent,
                            "_load_schema",
                            return_value={"description": "test schema"},
                        ):
                            agent = llm_agent.JianyingAgent(api_key="test-key")
        finally:
            sys.path.pop(0)

        self.assertEqual(agent.model, "glm-4-flash")


if __name__ == "__main__":
    unittest.main()
