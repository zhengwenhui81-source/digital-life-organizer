"""The planner accepts useful plans and rejects unsafe model output."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from fileforge.agent import plan_task, validate_plan
from fileforge.agent.executor import ToolRouter
from fileforge.agent.service import TaskConflict, TaskService


def test_plan_task_generates_contract_fields(tmp_path: Path) -> None:
    def generate(prompt: str) -> str:
        assert "hackathon" in prompt
        assert str(tmp_path) in prompt
        assert "list_files(workspace: string" in prompt
        assert "Use workspace, never path, for list_files" in prompt
        return json.dumps(
            {
                "steps": [
                    {
                        "tool": "search_files",
                        "description": "Find notices",
                        "arguments": {
                            "workspace": str(tmp_path),
                            "query": "hackathon",
                            "extensions": [],
                        },
                    },
                    {
                        "tool": "copy_file",
                        "description": "Copy selected file",
                        "arguments": {"source": "", "destination": ""},
                    },
                ]
            }
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
            "task_001",
            "goal",
        )


def test_model_cannot_set_risk_or_status() -> None:
    plan = validate_plan(
        {
            "steps": [
                {
                    "tool": "move_file",
                    "description": "archive",
                    "arguments": {"source": "", "destination": ""},
                    "risk": "low",
                    "status": "completed",
                }
            ]
        },
        "task_001",
        "goal",
    )
    assert plan["steps"][0]["risk"] == "medium"
    assert plan["steps"][0]["status"] == "pending"


@pytest.mark.parametrize(
    "tool,arguments,invalid",
    [
        ("list_files", {"path": "/somewhere"}, "path"),
        ("list_files", {}, "workspace"),
        ("list_files", {"workspace": "/somewhere", "path": "/other"}, "path"),
        ("search_files", {"workspace": "/somewhere", "path": "x"}, "path"),
        ("search_files", {"workspace": "/somewhere"}, "query"),
        ("list_files", {"workspace": "/somewhere", "recursive": "yes"}, "recursive"),
    ],
)
def test_invalid_tool_arguments_fail_during_planning(tool, arguments, invalid):
    with pytest.raises(ValueError, match=invalid):
        validate_plan(
            {"steps": [{"tool": tool, "description": "Scan", "arguments": arguments}]},
            "task_001",
            "scan files",
        )


def test_router_rejects_invalid_resolved_arguments_before_call():
    called = False

    def scan(workspace: str) -> dict:
        nonlocal called
        called = True
        return {
            "success": True,
            "tool": "list_files",
            "data": {"files": []},
            "message": "ok",
            "error": None,
        }

    result = ToolRouter({"list_files": scan}).call("list_files", {"path": "x"})
    assert result["success"] is False
    assert "path" in result["error"]
    assert not called


def test_tool_call_exception_becomes_failed_task(tmp_path: Path):
    def broken_scan(workspace: str) -> dict:
        raise RuntimeError("Scanner unavailable")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "list_files",
                        "description": "List files",
                        "arguments": {"workspace": workspace},
                    }
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(
        planner=planner, router=ToolRouter({"list_files": broken_scan})
    )
    task_id = service.create("List files", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][0]["tool"] == "list_files"
    assert snapshot["results"][0]["success"] is False
    assert "Scanner unavailable" in snapshot["error"]
    assert snapshot["pending_operations"] == []
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)


def test_llm_plan_scans_real_workspace_without_writes(tmp_path: Path):
    (tmp_path / "first.txt").write_text("first")
    (tmp_path / "second.pdf").write_bytes(b"sample")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return plan_task(
            task_id,
            goal,
            workspace,
            generate=lambda prompt: json.dumps(
                {
                    "steps": [
                        {
                            "tool": "list_files",
                            "description": "List files",
                            "arguments": {"workspace": workspace},
                        }
                    ]
                }
            ),
        )

    service = TaskService(planner=planner)
    task_id = service.create("List files without writes", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["pending_operations"] == []
    names = {
        Path(item["path"]).name for item in snapshot["results"][0]["data"]["files"]
    }
    assert {"first.txt", "second.pdf"} <= names
    assert service.report(task_id)["status"] == "completed"


def test_invalid_response_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        plan_task("task_001", "goal", str(tmp_path), generate=lambda _: "not json")


@pytest.mark.parametrize("raw", ["", "  ", None])
def test_empty_response_rejected(tmp_path: Path, raw) -> None:
    with pytest.raises(ValueError, match="empty response"):
        plan_task("task_001", "goal", str(tmp_path), generate=lambda _: raw)


def test_valid_json_still_requires_valid_plan(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown or forbidden tool"):
        plan_task(
            "task_001",
            "goal",
            str(tmp_path),
            generate=lambda _: (
                '{"steps":[{"tool":"shell","description":"run","arguments":{}}]}'
            ),
        )


@pytest.mark.parametrize(
    "model,expected_json",
    [("gpt-4.1-mini", True), ("gpt-5-mini", True), ("qwen3-coder", False)],
)
def test_model_request_uses_json_mode_without_temperature(
    tmp_path: Path, monkeypatch, model: str, expected_json: bool
) -> None:
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "steps": [
                                        {
                                            "tool": "list_files",
                                            "description": "List",
                                            "arguments": {"workspace": str(tmp_path)},
                                        }
                                    ]
                                }
                            ),
                            refusal=None,
                        ),
                    )
                ]
            )

    monkeypatch.setitem(
        sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient, APIError=Exception)
    )
    plan_task(
        "task_001",
        "list files",
        str(tmp_path),
        model=model,
        base_url="https://api.openai.com/v1",
    )
    assert "temperature" not in calls[0]
    assert (calls[0].get("response_format") == {"type": "json_object"}) is expected_json


def test_planner_endpoint_uses_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FILEFORGE_AGENT_PLANNER_MODEL", "team-model")
    monkeypatch.setenv("FILEFORGE_AGENT_PLANNER_BASE_URL", "http://127.0.0.1:9999/v1")
    result = json.dumps(
        {
            "steps": [
                {
                    "tool": "list_files",
                    "description": "List",
                    "arguments": {"workspace": str(tmp_path)},
                }
            ]
        }
    )
    with patch("fileforge.agent.planner._generate_local", return_value=result) as call:
        plan_task("task_001", "goal", str(tmp_path))
    assert call.call_args.kwargs == {
        "model": "team-model",
        "base_url": "http://127.0.0.1:9999/v1",
    }


def test_demo_plan_uses_no_model_and_requires_approval(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FILEFORGE_AGENT_PLANNER_MODE", "demo")
    with patch("fileforge.agent.planner._generate_local") as call:
        plan = plan_task("task_001", "demo", str(tmp_path))
    call.assert_not_called()
    assert [step["tool"] for step in plan["steps"]] == [
        "list_files",
        "create_folder",
    ]
    assert [step["risk"] for step in plan["steps"]] == ["low", "medium"]
    assert plan["steps"][1]["arguments"]["path"] == str(tmp_path / "Agent_Dev_Demo_001")


@pytest.mark.parametrize("status", [400, 502])
def test_upstream_error_is_safe(tmp_path: Path, monkeypatch, status: int) -> None:
    class UpstreamError(Exception):
        status_code = status

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.fail))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def fail(self, **kwargs):
            raise UpstreamError("Bad Gateway")

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=FakeClient, APIError=UpstreamError),
    )
    with pytest.raises(
        RuntimeError, match=f"Planner model request failed \\(HTTP {status}"
    ) as error:
        plan_task(
            "task_001",
            "goal",
            str(tmp_path),
            base_url="https://api.openai.com/v1?token=secret",
        )
    assert "Bad Gateway" not in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "error_kind,expected",
    [
        ("connection", "connection failed"),
        ("timeout", "request timed out"),
        ("status", "HTTP 429"),
        ("other", "API error"),
    ],
)
def test_planner_sdk_error_category_is_safe(
    tmp_path: Path, monkeypatch, error_kind: str, expected: str
) -> None:
    class APIError(Exception):
        pass

    class APIConnectionError(APIError):
        pass

    class APITimeoutError(APIConnectionError):
        pass

    class APIStatusError(APIError):
        status_code = 429

    errors = {
        "connection": APIConnectionError,
        "timeout": APITimeoutError,
        "status": APIStatusError,
        "other": APIError,
    }

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.fail))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def fail(self, **kwargs):
            raise errors[error_kind]("Authorization: secret; document body")

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(
            OpenAI=FakeClient,
            APIError=APIError,
            APIConnectionError=APIConnectionError,
            APITimeoutError=APITimeoutError,
            APIStatusError=APIStatusError,
        ),
    )

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return plan_task(
            task_id,
            goal,
            workspace,
            base_url="https://example.test/v1?token=secret",
        )

    service = TaskService(planner=planner)
    task_id = service.create("scan files", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert expected in snapshot["error"]
    assert "secret" not in snapshot["error"]
    assert "Authorization" not in snapshot["error"]
    assert "document body" not in snapshot["error"]
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)
