"""Opt-in local HTTP acceptance with a controlled Plan and REAL C/D/A tools.

This is not an LLM or Fixture-response server. No tool results, approval state,
source snapshots or execution outcomes are substituted. Every write to Workspace
is made by the unmodified TaskService only after its ordinary approval endpoint.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def prepare(directory: Path, port: int) -> dict:
    if not directory.is_absolute() or not directory.parent.is_dir():
        raise ValueError("Use an absolute NEW directory with an existing parent")
    for ancestor in (directory.parent, *directory.parents):
        info = ancestor.lstat()
        if ancestor.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Links/reparse points are forbidden")
    directory.mkdir()  # exclusive: never reuse, overwrite, or clean a directory
    cases = {}
    for name in ("normal", "missing", "reject", "changed", "occupied", "partial_source_changed", "unrecognized_notice"):
        root = directory / name
        root.mkdir()
        notice = "必须提交报名表。"
        if name == "unrecognized_notice":
            notice = "报名时必须提交报名表。"
        if name == "missing":
            notice += "必须提交签字页。"
        if name == "partial_source_changed":
            notice += "必须提交附表。"
            (root / "附表.txt").write_text("受控部分失败验收：附表原始内容。", encoding="utf-8")
        (root / "通知.txt").write_text(notice, encoding="utf-8")
        (root / "报名表.txt").write_text("受控验收专用：报名表内容，不含个人资料。", encoding="utf-8")
        cases[name] = str(root)
    manifest = {"kind": "controlled-plan-real-tools-not-LLM", "directory": str(directory),
                "url": f"http://127.0.0.1:{port}", "cases": cases}
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def controlled_planner(allowed: set[Path]):
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        from fileforge.agent.planner import validate_plan

        root = Path(workspace)
        if root not in allowed:
            raise ValueError("Acceptance server only accepts its newly created Workspaces")
        steps = [
            ("list_files", {"workspace": workspace, "recursive": False}),
            ("read_document", {"path": str(root / "通知.txt")}),
            ("detect_conflicts", {}),
            ("extract_requirements", {}),
            ("read_document", {"path": str(root / "报名表.txt")}),
            *([("read_document", {"path": str(root / "附表.txt")})] if root.name == "partial_source_changed" else []),
            ("compare_versions", {}),
            ("match_requirements", {}),
            ("build_package", {}),
        ]
        return validate_plan({"steps": [{"tool": tool, "description": "Controlled acceptance: " + tool,
                                          "arguments": arguments} for tool, arguments in steps]}, task_id, goal)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a local unprivileged port")
    manifest = prepare(args.directory, args.port)
    from fileforge.agent.service import TaskService
    from fileforge.api.agent import get_service
    from fileforge.api.server import app
    import uvicorn

    service = TaskService(planner=controlled_planner({Path(p) for p in manifest["cases"].values()}))
    app.dependency_overrides[get_service] = lambda: service
    print(json.dumps(manifest, ensure_ascii=False), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
