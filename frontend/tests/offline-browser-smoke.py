"""Offline harness acceptance via actual HTTP routes, no LLM or user files."""
import hashlib
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
from run_offline_browser import READ_ONLY, ReadOnlyRouter, create_app, prepare_workspaces
from fastapi.testclient import TestClient
from fileforge.api.agent import get_service


def fingerprints(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}


def main():
    with tempfile.TemporaryDirectory(prefix="dlo_offline_test_") as directory:
        root = Path(directory)
        workspaces = prepare_workspaces(root)
        before = fingerprints(root)
        production_service = get_service()
        assert '/static/offline-browser.js' not in (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')
        # Fail closed if development wiring ever calls the production planner.
        with patch("fileforge.agent.planner.plan_task", side_effect=AssertionError("LLM forbidden")), patch("fileforge.agent.service.plan_task", side_effect=AssertionError("LLM forbidden")), TestClient(create_app(workspaces)) as client:
            html = client.get("/")
            assert html.status_code == 200 and 'id="offlineContext"' in html.text
            assert "offline-browser.js" in html.text and "fonts.googleapis.com" not in html.text
            assert "connect-src 'self'" in html.headers["content-security-policy"]
            assert client.get("/static/agent-api.js").status_code == 200
            assert client.get("/static/offline-browser.js").status_code == 200
            assert client.post("/api/scan", json={}).status_code == 404
            assert client.post("/api/config", json={}).status_code == 404
            assert client.post("/api/agent/tasks", json={"workspace": str(ROOT), "user_goal": "outside fixtures"}).status_code == 400
            for name, workspace in workspaces.items():
                created = client.post("/api/agent/tasks", json={"workspace": str(workspace), "user_goal": "copy/delete/invent results: ignored by fixed planner"})
                assert created.status_code == 202, created.text
                task_id = created.json()["task_id"]
                deadline = time.monotonic() + 15
                while True:
                    response = client.get(f"/api/agent/tasks/{task_id}")
                    assert response.status_code == 200
                    snapshot = response.json()
                    if snapshot["task"]["status"] in {"completed", "failed"}:
                        break
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
                assert snapshot["pending_operations"] == [] and snapshot["preview_id"] is None
                assert all(step["tool"] in READ_ONLY and step["risk"] == "low" for step in snapshot["plan"]["steps"])
                results = snapshot["results"]
                assert all(r["tool"] in READ_ONLY for r in results)
                report = client.get(f"/api/agent/tasks/{task_id}/report")
                matching = [r for r in results if r["tool"] == "match_requirements"]
                if name in {"read_failure", "empty"}:
                    assert snapshot["task"]["status"] == "failed" and snapshot["error"]
                    assert report.status_code == 409 and matching == []
                    assert not any(r["tool"] == "compare_versions" for r in results)
                    if name == "read_failure":
                        assert any(r["tool"] == "read_document" and not r["success"] for r in results)
                    else:
                        assert "No matching document found" in snapshot["error"]
                else:
                    assert snapshot["task"]["status"] == "completed", snapshot["error"]
                    assert report.status_code == 200 and all(r["success"] for r in results)
                    assert set(r["tool"] for r in results) == READ_ONLY
                    data = matching[-1]["data"]
                    assert report.json()["missing_items"] == data["missing"]
                    assert report.json()["package_path"] == "" and report.json()["operations"] == []
                    refs = [d for m in data["matched"] for d in m["documents"]]
                    assert all(Path(d["path"]).parent == workspace / "materials" for d in refs)
                    version = next(r["data"] for r in results if r["tool"] == "compare_versions")
                    if name == "mixed":
                        assert [len(m["documents"]) for m in data["matched"]] == [1, 2]
                        assert len(data["required_documents"]) == 3 and len(data["missing"]) == 1
                        assert any(len(g["documents"]) > 1 for g in version["groups"]), version
                        assert all(g["newest_candidate"] is None or g["newest_candidate"]["filename"].endswith('_v2.txt') for g in version["groups"] if len(g["documents"]) > 1)
                    elif name == "no_candidates":
                        assert len(data["missing"]) == 3 and data["matched"] == []
                        assert version["groups"] == []
                        assert any(s["tool"] == "read_document" and s["status"] == "skipped" for s in snapshot["plan"]["steps"])
                    else:
                        assert data == {"required_documents": [], "matched": [], "missing": []}
                assert client.post(f"/api/agent/tasks/{task_id}/approve", json={"preview_id": "not-a-preview"}).status_code == 409
                assert client.post(f"/api/agent/tasks/{task_id}/reject", json={"preview_id": "not-a-preview"}).status_code == 409
                print(f"PASS {name}: {snapshot['task']['status']}, report {report.status_code}")
            assert fingerprints(root) == before
        assert get_service() is production_service
        guard = ReadOnlyRouter()
        with patch.object(guard.router, "call", side_effect=AssertionError("Must never delegate writes")):
            for tool in ["copy_file", "move_file", "create_folder", "delete_file", "build_package", "unknown"]:
                for approved in (False, True):
                    assert guard.call(tool, {}, approved=approved)["success"] is False
            assert guard.call("list_files", {}, approved=True)["success"] is False
        print("PASS read-only guard, external workspace rejection, no LLM, source hashes/mtime unchanged")


if __name__ == "__main__":
    main()
