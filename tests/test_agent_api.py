"""The five Agent routes follow the agreed HTTP and approval contracts."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from fileforge.agent.service import TaskService
from fileforge.api.agent import get_service
from fileforge.api.server import app


def _plan(task_id: str, goal: str, workspace: str) -> dict:
    root = Path(workspace)
    return {
        "task_id": task_id, "goal": goal,
        "steps": [
            {"step_id": "step_001", "tool": "list_files",
             "description": "List files", "risk": "low", "status": "pending",
             "arguments": {"workspace": workspace}},
            {"step_id": "step_002", "tool": "copy_file",
             "description": "Copy selected file", "risk": "medium", "status": "pending",
             "arguments": {"source": str(root / "source.txt"),
                           "destination": str(root / "package.txt")}},
        ],
    }


def _wait(client: TestClient, task_id: str, expected: str) -> dict:
    for _ in range(100):
        response = client.get(f"/api/agent/tasks/{task_id}")
        snapshot = response.json()
        if snapshot["task"]["status"] in (expected, "failed"):
            return snapshot
        time.sleep(0.01)
    raise AssertionError("Task did not finish planning")


def test_create_snapshot_approve_and_report(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("source")
    service = TaskService(planner=_plan)
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post("/api/agent/tasks", json={
                "user_goal": "Prepare files", "workspace": str(tmp_path)
            })
            assert response.status_code == 202
            task_id = response.json()["task_id"]
            snapshot = _wait(client, task_id, "awaiting_approval")
            assert snapshot["task"]["status"] == "awaiting_approval"
            assert len(snapshot["results"]) == 1
            assert len(snapshot["pending_operations"]) == 1
            preview_id = snapshot["preview_id"]
            assert preview_id.startswith("sha256:")
            assert not (tmp_path / "package.txt").exists()
            assert client.get(f"/api/agent/tasks/{task_id}/report").status_code == 409
            assert client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={"preview_id": "sha256:wrong"},
            ).status_code == 409
            assert not (tmp_path / "package.txt").exists()

            approved = client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={"preview_id": preview_id},
            )
            assert approved.status_code == 200
            assert approved.json()["task"]["status"] == "completed"
            assert approved.json()["preview_id"] is None
            assert (tmp_path / "package.txt").read_text() == "source"
            report = client.get(f"/api/agent/tasks/{task_id}/report")
            assert report.status_code == 200
            assert report.json()["task_id"] == task_id
            assert client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={"preview_id": preview_id},
            ).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_reject_skips_mutation_and_duplicate_request_conflicts(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("source")
    service = TaskService(planner=_plan)
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            task_id = client.post("/api/agent/tasks", json={
                "user_goal": "Prepare files", "workspace": str(tmp_path)
            }).json()["task_id"]
            preview = _wait(client, task_id, "awaiting_approval")["preview_id"]
            rejected = client.post(
                f"/api/agent/tasks/{task_id}/reject",
                json={"preview_id": preview},
            )
            assert rejected.status_code == 200
            assert rejected.json()["task"]["status"] == "failed"
            assert rejected.json()["plan"]["steps"][1]["status"] == "skipped"
            assert rejected.json()["error"] == "User rejected pending operations"
            assert not (tmp_path / "package.txt").exists()
            assert client.post(
                f"/api/agent/tasks/{task_id}/reject",
                json={"preview_id": preview},
            ).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_invalid_workspace_and_unknown_task(tmp_path: Path) -> None:
    app.dependency_overrides[get_service] = lambda: TaskService(planner=_plan)
    try:
        with TestClient(app) as client:
            assert client.post("/api/agent/tasks", json={
                "user_goal": "goal", "workspace": str(tmp_path / "missing")
            }).status_code == 400
            assert client.post(
                "/api/agent/tasks", json={"user_goal": "goal"}
            ).status_code == 400
            assert client.post(
                "/api/agent/tasks", content="not-json",
                headers={"Content-Type": "application/json"},
            ).status_code == 400
            assert client.get("/api/agent/tasks/not-found").status_code == 404
            assert client.get("/api/agent/tasks/not-found/report").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_planned_file_operation_outside_workspace_fails(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"

    def unsafe_plan(task_id: str, goal: str, workspace: str) -> dict:
        plan = _plan(task_id, goal, workspace)
        plan["steps"][1]["arguments"]["destination"] = str(outside)
        return plan

    service = TaskService(planner=unsafe_plan)
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            task_id = client.post("/api/agent/tasks", json={
                "user_goal": "goal", "workspace": str(tmp_path)
            }).json()["task_id"]
            snapshot = _wait(client, task_id, "failed")
            assert snapshot["task"]["status"] == "failed"
            assert "escapes workspace" in snapshot["error"]
            assert not outside.exists()
    finally:
        app.dependency_overrides.clear()


def test_planning_failure_is_visible_in_snapshot(tmp_path: Path) -> None:
    def fail_planner(task_id: str, goal: str, workspace: str) -> dict:
        raise RuntimeError("Local planner unavailable")

    service = TaskService(planner=fail_planner)
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            task_id = client.post("/api/agent/tasks", json={
                "user_goal": "goal", "workspace": str(tmp_path)
            }).json()["task_id"]
            snapshot = _wait(client, task_id, "failed")
            assert snapshot["task"]["status"] == "failed"
            assert "unavailable" in snapshot["error"]
    finally:
        app.dependency_overrides.clear()
