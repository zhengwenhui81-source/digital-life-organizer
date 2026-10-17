"""Read-only verification of planned file operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def verify_result(task_id: str, expected: dict[str, Any], workspace: str) -> dict[str, Any]:
    """Check expected package and archive paths after execution.

    ``expected`` accepts ``files`` and ``archive`` lists of workspace-relative
    paths. Absolute paths and paths escaping the workspace are rejected.
    """
    tool = "verify_result"
    try:
        if not task_id.strip():
            raise ValueError("task_id is required")
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Workspace is not a directory: {root}")
        if not isinstance(expected, dict):
            raise ValueError("expected must be an object")
        checks = []
        for category in ("files", "archive"):
            paths = expected.get(category, [])
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                raise ValueError(f"expected.{category} must be a list of paths")
            for relative in paths:
                path = Path(relative)
                if path.is_absolute():
                    raise ValueError("Expected paths must be workspace-relative")
                resolved = (root / path).resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError("Expected path escapes workspace")
                checks.append(
                    {
                        "path": str(resolved),
                        "kind": category,
                        "passed": resolved.is_file(),
                    }
                )
        return {
            "success": True,
            "tool": tool,
            "data": {"checks": checks, "passed": all(c["passed"] for c in checks)},
            "message": "Verification completed",
            "error": None,
        }
    except (OSError, ValueError) as exc:
        return {
            "success": False,
            "tool": tool,
            "data": None,
            "message": "Verification failed",
            "error": str(exc),
        }
