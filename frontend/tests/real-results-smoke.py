"""Read-only HTTP/tool smoke check; fixed test planner, real backend tools.

Run with the project's Python environment. This does not certify LLM planning,
public matching, package execution, or classroom end-to-end acceptance.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fastapi.testclient import TestClient
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService
from fileforge.api.agent import get_service
from fileforge.api.server import app
from fileforge.document import read_document
from fileforge.task_intelligence import detect_conflicts, extract_requirements


def planner(task_id, goal, workspace):
    return validate_plan({"steps": [
        {"tool": "list_files", "description": "Discover runtime files", "arguments": {"workspace": workspace, "recursive": False}},
        {"tool": "read_document", "description": "Read discovered documents", "arguments": {}},
        {"tool": "compare_versions", "description": "Compare runtime candidates", "arguments": {}},
    ]}, task_id, goal)


def main():
    node_check = """
const fs=require('fs'), assert=require('assert/strict'), ui=require('./frontend/agent-results.js');
const snapshot=JSON.parse(fs.readFileSync(0,'utf8'));
assert.equal(snapshot.task.status,'completed');
for(const [name,render] of [['compare_versions',ui.versions],['detect_conflicts',ui.conflicts],['extract_requirements',ui.requirements]]){
 const html=render(ui.latest(snapshot.results,name));
 assert(!html.includes('工具执行失败'));
 assert(!html.includes('[object Object]'));
}
"""
    with tempfile.TemporaryDirectory(prefix="dlo_frontend_unknown_") as directory:
        root = Path(directory)
        service = TaskService(planner=planner)
        app.dependency_overrides[get_service] = lambda: service
        try:
            with TestClient(app) as client:
                for count in (0, 1, 2):
                    workspace = root / str(count)
                    workspace.mkdir()
                    for index in range(1, count + 1):
                        (workspace / f"课程说明_v{index}.txt").write_text(
                            "课程学习目标与评分说明。\n" * 30 + f"阶段成果说明 {index}\n", encoding="utf-8"
                        )
                    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in workspace.iterdir()}
                    created = client.post("/api/agent/tasks", json={"user_goal": "核对课程资料版本", "workspace": str(workspace)})
                    assert created.status_code == 202
                    task_id = created.json()["task_id"]
                    deadline = time.monotonic() + 15
                    while True:
                        snapshot = client.get(f"/api/agent/tasks/{task_id}").json()
                        if snapshot["task"]["status"] in ("completed", "failed"):
                            break
                        assert time.monotonic() < deadline, "Task did not finish"
                        time.sleep(0.02)
                    assert snapshot["task"]["status"] == "completed", snapshot["error"]
                    groups = next(r for r in snapshot["results"] if r["tool"] == "compare_versions")["data"]["groups"]
                    assert len(groups) == (0 if count == 0 else 1)
                    if count == 1:
                        assert groups[0]["newest_candidate"] is None
                    if count == 2:
                        assert groups[0]["newest_candidate"]["filename"] == "课程说明_v2.txt"
                    report = client.get(f"/api/agent/tasks/{task_id}/report")
                    assert report.status_code == 200
                    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in workspace.iterdir()} == hashes
                    # D remains called through its public entry points, not registered
                    # here as a substitute for the still-pending Agent integration.
                    documents = [read_document(str(p))["data"]["document"] for p in workspace.iterdir()]
                    snapshot["results"].extend([detect_conflicts(documents), extract_requirements(documents)])
                    subprocess.run(["node", "-e", node_check], input=json.dumps(snapshot), text=True, check=True, cwd=Path(__file__).resolve().parents[2])
                    print(f"PASS real HTTP + C/D public results -> frontend renderer: {count} runtime documents")
        finally:
            app.dependency_overrides.pop(get_service, None)


if __name__ == "__main__":
    main()
