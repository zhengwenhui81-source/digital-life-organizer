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
Resolver = Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]


class ToolRouter:
    """Route only public tools; document tools may register when available."""

    def __init__(self, extra_tools: dict[str, Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {
            "list_files": list_files,
            "search_files": search_files,
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
        except (OSError, TypeError, ValueError) as exc:
            return _failure(name, str(exc))
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
    state["status"] = "executing"
    state["pending_operations"] = []
    for step in state["plan"]["steps"]:
        if step["status"] == "completed":
            continue
        if step["status"] not in {"pending", "awaiting_approval"}:
            raise ValueError("Execution contains an invalid step status")
        name = step["tool"]
        if name not in TOOL_RISKS or step["risk"] != TOOL_RISKS[name]:
            raise ValueError("Execution contains an invalid tool risk")
        if step["risk"] == "medium" and not approve_all:
            step["status"] = "awaiting_approval"
            state["status"] = "awaiting_approval"
            state["pending_operations"] = [
                deepcopy(s) for s in state["plan"]["steps"]
                if s["risk"] == "medium" and s["status"] != "completed"
            ]
            return state
        arguments = (
            resolver(step, state["results"]) if resolver else step["arguments"]
        )
        if not isinstance(arguments, dict):
            raise ValueError("Resolver must return tool arguments")
        step["status"] = "running"
        result = router.call(name, arguments, approved=approve_all)
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
