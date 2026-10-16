"""The planner accepts useful plans and rejects unsafe model output."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pytest

from fileforge.agent import plan_task, validate_plan


def test_plan_task_generates_contract_fields(tmp_path: Path) -> None:
    def generate(prompt: str) -> str:
        assert "hackathon" in prompt
        assert str(tmp_path) in prompt
        return json.dumps(
            {"steps": [
                {"tool": "search_files", "description": "Find notices",
                 "arguments": {"workspace": str(tmp_path), "query": "hackathon",
                               "extensions": []}},
                {"tool": "copy_file", "description": "Copy selected file",
                 "arguments": {"source": "", "destination": ""}},
            ]}
        )

    plan = plan_task(
        "task_001", "Prepare hackathon files", str(tmp_path), generate=generate
    )
    assert plan["task_id"] == "task_001"
    assert plan["goal"] == "Prepare hackathon files"
    assert plan["steps"][0]["step_id"] == "step_001"
    assert plan["steps"][0]["risk"] == "low"
    assert plan["steps"][1]["risk"] == "medium"
    assert all(step["status"] == "pending" for step in plan["steps"])


@pytest.mark.parametrize("tool", ["delete_file", "overwrite_file", "shell"])
def test_forbidden_tool_rejected(tool: str) -> None:
    with pytest.raises(ValueError, match="unknown or forbidden"):
        validate_plan(
            {"steps": [{"tool": tool, "description": "unsafe", "arguments": {}}]},
            "task_001", "goal",
        )


def test_model_cannot_set_risk_or_status() -> None:
    plan = validate_plan(
        {"steps": [{"tool": "move_file", "description": "archive",
                    "arguments": {}, "risk": "low", "status": "completed"}]},
        "task_001", "goal",
    )
    assert plan["steps"][0]["risk"] == "medium"
    assert plan["steps"][0]["status"] == "pending"


def test_invalid_response_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        plan_task("task_001", "goal", str(tmp_path), generate=lambda _: "not json")


def test_planner_endpoint_uses_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FILEFORGE_AGENT_PLANNER_MODEL", "team-model")
    monkeypatch.setenv("FILEFORGE_AGENT_PLANNER_BASE_URL", "http://127.0.0.1:9999/v1")
    result = json.dumps({"steps": [{"tool": "list_files", "description": "List",
                                    "arguments": {"workspace": str(tmp_path)}}]})
    with patch("fileforge.agent.planner._generate_local", return_value=result) as call:
        plan_task("task_001", "goal", str(tmp_path))
    assert call.call_args.kwargs == {
        "model": "team-model", "base_url": "http://127.0.0.1:9999/v1"
    }


def test_demo_plan_uses_no_model_and_requires_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FILEFORGE_AGENT_PLANNER_MODE", "demo")
    with patch("fileforge.agent.planner._generate_local") as call:
        plan = plan_task("task_001", "demo", str(tmp_path))
    call.assert_not_called()
    assert [step["tool"] for step in plan["steps"]] == ["list_files", "create_folder"]
    assert [step["risk"] for step in plan["steps"]] == ["low", "medium"]
    assert plan["steps"][1]["arguments"]["path"] == str(tmp_path / "Agent_Dev_Demo_001")


def test_upstream_502_becomes_actionable_task_error(tmp_path: Path, monkeypatch) -> None:
    class UpstreamError(Exception):
        status_code = 502

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.fail))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def fail(self, **kwargs):
            raise UpstreamError("Bad Gateway")

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(
        OpenAI=FakeClient, APIError=UpstreamError
    ))
    with pytest.raises(RuntimeError, match="Planner model unavailable \\(HTTP 502") as error:
        plan_task("task_001", "goal", str(tmp_path),
                  base_url="http://127.0.0.1:11434/v1")
    assert "FILEFORGE_AGENT_PLANNER_MODE=demo" in str(error.value)
