"""Approval request parsing and fail-closed Package risk handling."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from fileforge.agent.service import TaskConflict, TaskService
from fileforge.api.agent import _approve_body, _body, approve_task, reject_task


class _Request:
    def __init__(self, data):
        self.data = data

    async def json(self):
        return self.data


def _plan(task_id: str, goal: str, workspace: str) -> dict:
    return {
        "task_id": task_id,
        "goal": goal,
        "steps": [
            {
                "step_id": "step_001",
                "tool": "create_folder",
                "description": "Create a folder after approval",
                "risk": "medium",
                "status": "pending",
                "arguments": {"path": str(Path(workspace) / "approved")},
            }
        ],
    }


def _pending(tmp_path: Path) -> tuple[TaskService, str, str]:
    service = TaskService(planner=_plan)
    task_id = service.create("Create folder", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "awaiting_approval"
    return service, task_id, snapshot["preview_id"]


def test_approve_body_accepts_only_exact_optional_boolean():
    assert asyncio.run(_approve_body(_Request({"preview_id": "sha256:x"}))) == {
        "preview_id": "sha256:x"
    }
    assert asyncio.run(
        _approve_body(_Request({"preview_id": "sha256:x", "accept_incomplete": True}))
    ) == {"preview_id": "sha256:x", "accept_incomplete": True}
    for body in (
        {},
        {"preview_id": " "},
        {"preview_id": "sha256:x", "accept_incomplete": 1},
        {"preview_id": "sha256:x", "accept_incomplete": None},
        {"preview_id": "sha256:x", "extra": True},
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(_approve_body(_Request(body)))
        assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            _body(
                _Request({"preview_id": "sha256:x", "accept_incomplete": True}),
                {"preview_id"},
            )
        )
    assert exc.value.status_code == 400  # Reject keeps its original request body.


def test_incomplete_package_gate_preserves_preview_and_never_writes(tmp_path: Path):
    service, task_id, preview_id = _pending(tmp_path)
    service._tasks[task_id]["package_approval"] = {
        "preview_id": preview_id,
        "plan_id": "package_plan_" + "a" * 32,
        "plan_sha256": "sha256:" + "b" * 64,
        "missing": ["报名表"],
        "unresolved": [{"kind": "selection_pending"}],
    }
    with pytest.raises(TaskConflict, match="specific risks"):
        service.decide(task_id, preview_id, approve=True)
    assert service.snapshot(task_id)["preview_id"] == preview_id
    assert not (tmp_path / "approved").exists()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            approve_task(task_id, _Request({"preview_id": preview_id}), service)
        )
    assert exc.value.status_code == 409
    assert service.snapshot(task_id)["preview_id"] == preview_id

    with pytest.raises(TaskConflict, match="not available"):
        service.decide(task_id, preview_id, approve=True, accept_incomplete=True)
    assert service.snapshot(task_id)["preview_id"] == preview_id
    assert not (tmp_path / "approved").exists()

    rejected = service.decide(task_id, preview_id, approve=False)
    assert rejected["task"]["status"] == "failed"
    assert rejected["preview_id"] is None
    assert not (tmp_path / "approved").exists()


def test_package_binding_mismatch_rejects_even_with_risk_acceptance(tmp_path: Path):
    service, task_id, preview_id = _pending(tmp_path)
    service._tasks[task_id]["package_approval"] = {
        "preview_id": "sha256:old",
        "plan_id": "package_plan_" + "a" * 32,
        "plan_sha256": "sha256:" + "b" * 64,
        "missing": [],
        "unresolved": [],
    }
    with pytest.raises(TaskConflict, match="not bound"):
        service.decide(task_id, preview_id, approve=True, accept_incomplete=True)
    assert service.snapshot(task_id)["preview_id"] == preview_id
    assert not (tmp_path / "approved").exists()

    with pytest.raises(TaskConflict, match="Rejection cannot accept"):
        service.decide(task_id, preview_id, approve=False, accept_incomplete=True)
    assert service.snapshot(task_id)["preview_id"] == preview_id


def test_ordinary_approval_is_compatible_with_optional_flag(tmp_path: Path):
    service, task_id, preview_id = _pending(tmp_path)
    approved = asyncio.run(
        approve_task(
            task_id,
            _Request({"preview_id": preview_id, "accept_incomplete": True}),
            service,
        )
    )
    assert approved["task"]["status"] == "completed"
    assert (tmp_path / "approved").is_dir()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(reject_task(task_id, _Request({"preview_id": preview_id}), service))
    assert exc.value.status_code == 409
