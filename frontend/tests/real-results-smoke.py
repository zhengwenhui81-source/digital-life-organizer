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
const version=ui.latest(snapshot.results,'compare_versions');
if(snapshot.task.status==='failed'){
 assert.equal(version,undefined);
 assert.match(ui.versions(version),/未执行/);
} else {
 assert.equal(snapshot.task.status,'completed');
 assert.equal(version.success,true);
 assert(!ui.versions(version).includes('工具执行失败'));
}
for(const [name,render] of [['detect_conflicts',ui.conflicts],['extract_requirements',ui.requirements]]){
 const result=ui.latest(snapshot.results,name);
 assert.equal(result.success,true);
 const html=render(result);
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
                    originals = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in workspace.iterdir()}
                    created = client.post("/api/agent/tasks", json={"user_goal": "核对课程资料版本", "workspace": str(workspace)})
                    assert created.status_code == 202
                    task_id = created.json()["task_id"]
                    deadline = time.monotonic() + 15
                    while True:
                        response = client.get(f"/api/agent/tasks/{task_id}")
                        assert response.status_code == 200
                        snapshot = response.json()
                        if snapshot["task"]["status"] in ("completed", "failed"):
                            break
                        assert time.monotonic() < deadline, "Task did not finish"
                        time.sleep(0.02)
                    report = client.get(f"/api/agent/tasks/{task_id}/report")
                    if count == 0:
                        assert snapshot["task"]["status"] == "failed"
                        assert "No matching document found" in snapshot["error"]
                        assert "read_document was not called" in snapshot["error"]
                        assert [r["tool"] for r in snapshot["results"]] == ["list_files"]
                        assert snapshot["results"][0]["success"] is True
                        assert snapshot["results"][0]["data"]["files"] == []
                        assert all(step["status"] != "completed" for step in snapshot["plan"]["steps"] if step["tool"] in {"read_document", "compare_versions"})
                        assert snapshot["pending_operations"] == []
                        assert snapshot["preview_id"] is None
                        assert report.status_code == 409
                        assert report.json()["detail"]
                    else:
                        assert snapshot["task"]["status"] == "completed", snapshot["error"]
                        reads = [r for r in snapshot["results"] if r["tool"] == "read_document"]
                        assert len(reads) == count and all(r["success"] for r in reads)
                        version = next(r for r in snapshot["results"] if r["tool"] == "compare_versions")
                        assert version["success"] is True
                        groups = version["data"]["groups"]
                        assert len(groups) == 1
                        if count == 1:
                            assert groups[0]["newest_candidate"] is None
                        if count == 2:
                            assert groups[0]["newest_candidate"]["filename"] == "课程说明_v2.txt"
                        assert report.status_code == 200
                        assert report.json()["task_id"] == task_id
                        assert report.json()["status"] == "completed"
                        assert report.json()["version_groups"] == groups
                    # Independently check D public outputs -> UI, not Agent routing.
                    documents = [read_document(str(p))["data"]["document"] for p in workspace.iterdir()]
                    snapshot["results"].extend([detect_conflicts(documents), extract_requirements(documents)])
                    subprocess.run(["node", "-e", node_check], input=json.dumps(snapshot), text=True, check=True, cwd=Path(__file__).resolve().parents[2])
                    assert {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in workspace.iterdir()} == originals
                    print(f"PASS real HTTP + C/D public results -> frontend renderer: {count} runtime documents ({snapshot['task']['status']}, report {report.status_code})")
        finally:
            app.dependency_overrides.pop(get_service, None)


if __name__ == "__main__":
    main()
