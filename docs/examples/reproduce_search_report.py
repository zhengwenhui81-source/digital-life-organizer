"""Check A's search/report mapping without replacing tools or resolver.

Historical gap baseline: 5df6777dbe385f7e83167445262c95e698b3e9e1.
PR #25 is merged; a post-merge recheck retains both listing/search discoveries.
This script observes either baseline without asserting that the old gap persists.
Run from an installed project environment; only temporary fixtures are written.
Exit zero means the reproduction ran, not that the report mapping is correct.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService


def run_case(root: Path, collection: str) -> dict:
    def planner(task_id: str, goal: str, workspace: str) -> dict:
        arguments = {"workspace": workspace}
        if collection == "search_files":
            arguments["query"] = "material"
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": tool,
                        "description": f"Acceptance: {tool}",
                        "arguments": arguments if tool == collection else {},
                    }
                    for tool in (collection, "read_document", "compare_versions")
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=planner)
    task_id = service.create("Compare this unknown workspace", str(root))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed", snapshot["error"]
    results = snapshot["results"]
    assert [r["tool"] for r in results] == [
        collection,
        "read_document",
        "read_document",
        "compare_versions",
    ]
    assert all(r["success"] for r in results)
    groups = results[-1]["data"]["groups"]
    assert len(groups) == 1
    assert groups[0]["newest_candidate"]["filename"] == "material_v2.txt"
    assert groups[0]["changes"]
    report = service.report(task_id)
    assert report["version_groups"] == groups
    key = "files" if collection == "list_files" else "matches"
    discovered = results[0]["data"][key]
    return {
        "collection": collection,
        "task_status": snapshot["task"]["status"],
        "discovered": len(discovered),
        "read_documents": sum(r["tool"] == "read_document" for r in results),
        "version_groups": len(report["version_groups"]),
        "found_files": len(report["found_files"]),
        "found_paths_match_discovery": {f["path"] for f in report["found_files"]}
        == {f["path"] for f in discovered},
    }


def main() -> None:
    with TemporaryDirectory(prefix="c-a-report-check-") as directory:
        root = Path(directory)
        for version, tail in (("v1", "old evidence"), ("v2", "new evidence")):
            path = root / f"material_{version}.txt"
            path.write_text("shared information " * 30 + "\n" + tail, encoding="utf-8")
            os.utime(path, ns=(1_760_000_000_000_000_000,) * 2)
        before = {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()
        }
        results = [run_case(root, name) for name in ("list_files", "search_files")]
        assert before == {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()
        }
        print(json.dumps({"cases": results, "sources_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
