"""Offline acceptance preparation only: no backend imports or material reads/writes."""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "demo/package_acceptance/course-materials-22.json"


def inspect_checklist(value):
    rows = value.get("items") if isinstance(value, dict) else None
    valid = isinstance(rows, list) and len(rows) == 22
    if valid:
        valid = all(
            isinstance(row, dict)
            and row.get("slot") == index
            and all(key in row and row[key] is None for key in (
                "filename", "extension", "file_type", "readability", "expected_handling"
            ))
            and row.get("status") == "待提供"
            for index, row in enumerate(rows, 1)
        )
    return {"template_valid": valid, "status": "blocked", "verified_files": 0,
            "required_files": 22, "reason": "实际材料待提供" if valid else "清单模板无效"}


def inspect_capabilities(executor_source, service_source):
    """Report static declarations, never certify runtime registration or safety."""
    executor = ast.parse(executor_source)
    service = ast.parse(service_source)
    registered = set()
    for node in ast.walk(executor):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute)
                and node.target.attr == "_tools" and isinstance(node.value, ast.Dict)):
            registered.update(key.value for key in node.value.keys
                              if isinstance(key, ast.Constant) and isinstance(key.value, str))
    limit = None
    for node in service.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_MAX_CANDIDATE_READS"
            for target in node.targets
        ) and isinstance(node.value, ast.Constant):
            limit = node.value.value
    required = {"plan_package", "build_package", "write_package_report"}
    return {"status": "blocked", "evidence_kind": "static_source_only",
            "runtime_execution_verified": False,
            "missing_default_router_tools": sorted(required - registered),
            "execution_unavailable_guard_present": any(
                isinstance(node, ast.Constant)
                and node.value == "Package execution is not available"
                for node in ast.walk(service)),
            "candidate_read_limit": limit,
            "reason": "仍需 A 的适配器及真实隔离验收；静态声明不证明可执行"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("checklist", "capabilities"))
    args = parser.parse_args(argv)
    if args.mode == "checklist":
        result = inspect_checklist(json.loads(CHECKLIST.read_text(encoding="utf-8")))
    else:
        result = inspect_capabilities(
            (ROOT / "src/fileforge/agent/executor.py").read_text(encoding="utf-8"),
            (ROOT / "src/fileforge/agent/service.py").read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 2  # Preparation blockers are expected, never an execution pass.


if __name__ == "__main__":
    raise SystemExit(main())
