"""Sequential tool execution with an explicit approval pause."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from fileforge.agent.planner import TOOL_RISKS, validate_plan
from fileforge.tools import (
    copy_file,
    create_folder,
    find_duplicates,
    list_files,
    move_file,
    search_files,
    verify_result,
)

Tool = Callable[..., dict[str, Any]]
Resolver = Callable[
    [dict[str, Any], list[dict[str, Any]]],
    dict[str, Any] | list[dict[str, Any]],
]


def _read_document(**arguments: Any) -> dict[str, Any]:
    # Load the parser only when this tool runs; other Agent tools stay usable
    # in environments where optional document formats are unavailable.
    from fileforge.document import read_document

    return read_document(**arguments)


def _compare_versions(**arguments: Any) -> dict[str, Any]:
    from fileforge.document import compare_versions

    return compare_versions(**arguments)


class ToolRouter:
    """Route only public tools; document tools may register when available."""

    def __init__(self, extra_tools: dict[str, Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {
            "list_files": list_files,
            "search_files": search_files,
            "read_document": _read_document,
            "compare_versions": _compare_versions,
            "find_duplicates": find_duplicates,
            "create_folder": create_folder,
            "copy_file": copy_file,
            "move_file": move_file,
            "verify_result": verify_result,
        }
        for name, function in (extra_tools or {}).items():
            if name not in TOOL_RISKS:
                raise ValueError(f"Unknown public tool: {name}")
            self._tools[name] = function

    def call(
        self, name: str, arguments: dict[str, Any], *, approved: bool = False
    ) -> dict[str, Any]:
        if name not in TOOL_RISKS or name not in self._tools:
            return _failure(name, "Tool is unavailable")
        if "approved" in arguments:
            return _failure(name, "Approval cannot be supplied in tool arguments")
        kwargs = dict(arguments)
        if TOOL_RISKS[name] == "medium":
            if not approved:
                return _failure(name, "User approval is required")
            # The built-in file tools enforce approval independently as well.
            if name in {"create_folder", "copy_file", "move_file"}:
                kwargs["approved"] = True
        try:
            result = self._tools[name](**kwargs)
        except Exception as exc:
            return _failure(name, str(exc) or type(exc).__name__)
        if (
            not isinstance(result, dict)
            or result.get("tool") != name
            or not isinstance(result.get("success"), bool)
            or not all(key in result for key in ("data", "message", "error"))
        ):
            return _failure(name, "Tool returned an invalid ToolResult")
        return result


def _failure(tool: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "tool": tool,
        "data": None,
        "message": f"{tool} failed",
        "error": error,
    }


def create_execution(plan: dict[str, Any]) -> dict[str, Any]:
    """Create internal task state from a validated contract-shaped Plan."""
    normalized = validate_plan(plan, plan["task_id"], plan["goal"])
    return {
        "task_id": normalized["task_id"],
        "status": "created",
        "plan": deepcopy(normalized),
        "results": [],
        "pending_operations": [],
    }


def execute(
    state: dict[str, Any],
    router: ToolRouter,
    *,
    approve_all: bool = False,
    resolver: Resolver | None = None,
) -> dict[str, Any]:
    """Run pending steps until completion, failure, or a medium-risk step."""
    if state["status"] in {"completed", "failed"}:
        return state
    if state["status"] == "awaiting_approval" and not approve_all:
        return state
    approved_preview = (
        {item["step_id"]: item for item in state["pending_operations"]}
        if approve_all
        else {}
    )
    state["status"] = "executing"
    state["pending_operations"] = []
    steps = state["plan"]["steps"]
    for index, step in enumerate(steps):
        if step["status"] == "completed":
            continue
        if step["status"] not in {"pending", "awaiting_approval"}:
            raise ValueError("Execution contains an invalid step status")
        name = step["tool"]
        if name not in TOOL_RISKS or step["risk"] != TOOL_RISKS[name]:
            raise ValueError("Execution contains an invalid tool risk")
        if step["risk"] == "medium" and step["step_id"] not in approved_preview:
            preview = []
            for candidate in steps[index:]:
                if candidate["risk"] != "medium":
                    break
                arguments = (
                    resolver(candidate, state["results"])
                    if resolver
                    else candidate["arguments"]
                )
                if not isinstance(arguments, dict):
                    raise ValueError("Resolver must return tool arguments")
                item = deepcopy(candidate)
                item["arguments"] = deepcopy(arguments)
                item["status"] = "awaiting_approval"
                preview.append(item)
                candidate["status"] = "awaiting_approval"
            state["status"] = "awaiting_approval"
            state["pending_operations"] = preview
            return state
        arguments = (
            approved_preview[step["step_id"]]["arguments"]
            if step["step_id"] in approved_preview
            else resolver(step, state["results"]) if resolver else step["arguments"]
        )
        if isinstance(arguments, list):
            if (
                name != "read_document"
                or step["risk"] != "low"
                or not all(isinstance(item, dict) for item in arguments)
            ):
                raise ValueError("Only read_document can resolve to a document batch")
            calls = arguments
        elif isinstance(arguments, dict):
            calls = [arguments]
        else:
            raise ValueError("Resolver must return tool arguments")
        step["status"] = "running"
        for call in calls:
            result = router.call(
                name, call, approved=step["step_id"] in approved_preview
            )
            state["results"].append(result)
            if not result["success"]:
                step["status"] = "failed"
                state["status"] = "failed"
                return state
        step["status"] = "completed"
    state["status"] = "completed"
    return state


def reject(state: dict[str, Any]) -> dict[str, Any]:
    """Reject proposed file operations without running them."""
    if state["status"] != "awaiting_approval":
        raise ValueError("Task is not awaiting approval")
    for step in state["plan"]["steps"]:
        if step["status"] in {"pending", "awaiting_approval"}:
            step["status"] = "skipped"
    state["pending_operations"] = []
    state["status"] = "failed"
    return state
