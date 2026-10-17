"""Local C-to-D development demo; not Agent registration or UI integration."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fileforge.document import read_document
from fileforge.task_intelligence import detect_conflicts, extract_requirements


def _analyze_paths(paths: list[Path]) -> dict[str, Any]:
    """Demo-only composition: never pass a failed read to either D tool."""
    reads = [read_document(path=str(path)) for path in paths]
    if any(not result["success"] for result in reads):
        return {"read_results": reads, "analysis": None}
    documents = [result["data"]["document"] for result in reads]
    return {
        "read_results": reads,
        "analysis": {
            "detect_conflicts": detect_conflicts(documents=documents),
            "extract_requirements": extract_requirements(documents=documents),
        },
    }


def main() -> int:
    """Create only disposable fixtures, print JSON, then clean them up."""
    with TemporaryDirectory(prefix="fileforge-c-d-demo-") as directory:
        root = Path(directory)
        paths = [root / "比赛通知.txt", root / "补充通知.txt"]
        paths[0].write_text(
            "报名截止：2026-10-18\n提交材料：\n1. 报名表\n2. 学生证（必交）\n",
            encoding="utf-8",
        )
        paths[1].write_text(
            "报名截止：2026-10-20\n无需提交学生证；必须提交项目介绍\n",
            encoding="utf-8",
        )
        report = _analyze_paths(paths)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        analysis = report["analysis"]
        return 0 if analysis and all(r["success"] for r in analysis.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
