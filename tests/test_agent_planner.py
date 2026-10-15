"""The planner accepts useful plans and rejects unsafe model output."""

from __future__ import annotations

import json
from pathlib import Path

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
