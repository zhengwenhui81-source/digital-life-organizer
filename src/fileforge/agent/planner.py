"""Generate and validate a contract-shaped plan from a natural-language goal."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# The public names and risk levels are fixed by API_CONTRACT.md. This is an
# internal validation map, not a second public contract.
TOOL_RISKS = {
    "list_files": "low",
    "search_files": "low",
    "read_document": "low",
    "find_duplicates": "low",
    "compare_versions": "low",
    "detect_conflicts": "low",
    "extract_requirements": "low",
    "match_requirements": "low",
    "verify_result": "low",
    "create_folder": "medium",
    "copy_file": "medium",
    "move_file": "medium",
    "build_package": "medium",
}

# Internal call signatures for tools currently routed by the Agent. Empty
# document arguments are resolved from successful reads before invocation.
_TOOL_ARGUMENTS = {
    "list_files": ({"workspace": str}, {"recursive": bool}),
    "search_files": ({"workspace": str, "query": str}, {"extensions": list}),
    "read_document": ({"path": str}, {}),
    "find_duplicates": ({"workspace": str}, {}),
    "compare_versions": ({"documents": list}, {}),
    "detect_conflicts": ({"documents": list}, {}),
    "extract_requirements": ({"documents": list}, {}),
    "match_requirements": (
        {"required_documents": list, "candidate_documents": list},
        {},
    ),
    "verify_result": ({"task_id": str, "expected": dict, "workspace": str}, {}),
    "create_folder": ({"path": str}, {}),
    "copy_file": ({"source": str, "destination": str}, {}),
    "move_file": ({"source": str, "destination": str}, {}),
    "build_package": (
        {"task_id": str, "plan_id": str, "plan_sha256": str},
        {},
    ),
}


def validate_tool_arguments(
    tool: str, arguments: dict[str, Any], *, planning: bool = False
) -> None:
    """Reject invented call fields before a Python tool receives them."""
    if tool not in _TOOL_ARGUMENTS:
        return  # Unregistered tools are rejected by ToolRouter.
    required, optional = _TOOL_ARGUMENTS[tool]
    if planning and tool == "build_package":
        if arguments:
            raise ValueError("build_package planning arguments must be empty")
        return
    unknown = set(arguments) - set(required) - set(optional)
    if unknown:
        raise ValueError(f"{tool} has unknown argument: {sorted(unknown)[0]}")
    if (
        planning
        and not arguments
        and tool
        in {
            "read_document",
            "compare_versions",
            "detect_conflicts",
            "extract_requirements",
            "match_requirements",
            "create_folder",
            "copy_file",
            "move_file",
        }
    ):
        return
    missing = set(required) - set(arguments)
    if missing:
        raise ValueError(f"{tool} is missing argument: {sorted(missing)[0]}")
    for key, value in arguments.items():
        expected = (required | optional)[key]
        if key == "extensions" and value is None:
            continue
        if type(value) is not expected:
            raise ValueError(f"{tool}.{key} must be {expected.__name__}")
        if key == "extensions" and not all(type(item) is str for item in value):
            raise ValueError("search_files.extensions must contain strings")
        if key == "documents" and not all(type(item) is dict for item in value):
            raise ValueError(f"{tool}.documents must contain objects")
        if key == "candidate_documents" and not all(
            type(item) is dict for item in value
        ):
            raise ValueError(
                "match_requirements.candidate_documents must contain objects"
            )
        if key == "required_documents" and not all(type(item) is str for item in value):
            raise ValueError(
                "match_requirements.required_documents must contain strings"
            )


_PROMPT = """Plan a local file task. Respond with JSON only, as an object with a
"steps" array. Each step must contain "tool", "description", and "arguments".
Use only these tool names: {tools}.
Tool arguments: list_files(workspace: string, recursive?: boolean);
search_files(workspace: string, query: string, extensions?: string[]);
read_document(path: string) or empty object after collection;
compare_versions(documents: object[]), detect_conflicts(documents: object[]),
extract_requirements(documents: object[]) or empty object after reads;
match_requirements(required_documents: string[], candidate_documents: object[])
or empty object after requirement extraction and candidate reads;
find_duplicates(workspace: string); verify_result(task_id: string,
expected: object, workspace: string); create_folder(path: string);
copy_file(source: string, destination: string);
move_file(source: string, destination: string).
For a material submission/check/package goal, use this order: search_files for
notices/rules; read_document {{}}; extract_requirements {{}}; detect_conflicts
{{}}; search_files separately for candidate materials; read_document {{}};
match_requirements {{}}. If packaging was requested, put build_package {{}}
last. Use empty arguments for reads and analysis so the server binds actual
successful results; never write Document or requirement data into the Plan.
The package step only
requests a read-only frozen proposal; the server will propose unique filename
candidates and require explicit preview approval before any write. Do not put
build_package in a scan-only task or invent selected files, IDs, or output paths.
Use workspace, never path, for list_files and search_files. Use exactly the
listed argument names; do not invent extra fields.
Read and analysis steps should precede file changes. Include only steps that
serve the goal. Do not invent filenames, file contents, or results. When an
argument depends on a previous result, use an empty object or list placeholder.
To analyze unknown workspace documents, collect candidates with list_files or
search_files, then use read_document with empty arguments to read each supported
candidate. A following compare_versions with empty arguments compares documents
read after that collection. A failed read stops the task.
For detect_conflicts or extract_requirements, collect and read the relevant
notice/rule documents first, then use empty arguments. Keep notice/rule documents
separate from candidate materials; a material mentioned in a notice is not an
existing candidate file. Do not guess document roles from a fixed demo filename.
For filename candidate matching, extract requirements from read notices first,
then separately collect and read candidate materials, then call
match_requirements with empty arguments. Filename matches are only candidates,
not proof that materials are valid or complete.
Never plan deletion or overwrite. File-changing steps will require user approval.
Workspace: {workspace}
Goal: {goal}
"""


def _material_goal(goal: str) -> tuple[bool, bool]:
    lowered = goal.casefold()
    package = any(word in lowered for word in ("打包", "材料包", "资料包")) or bool(
        re.search(r"\bpackage\b", lowered)
    )
    material = (
        package
        or (
            any(word in lowered for word in ("材料", "资料", "提交要求", "证明文件"))
            and any(
                word in lowered
                for word in ("核对", "检查", "匹配", "齐全", "缺少", "缺失", "准备")
            )
        )
        or bool(
            re.search(r"\b(check|match|verify|audit)\b", lowered)
            and re.search(r"\b(submission|requirements|materials)\b", lowered)
        )
    )
    return material, package


def _validate_material_sequence(steps: list[dict[str, Any]], goal: str) -> None:
    material, package = _material_goal(goal)
    if not material:
        return
    names = [step["tool"] for step in steps]
    # The planner cannot know the number of matched rule files before search
    # executes, so always include the read-only conflict check.
    sequence = (
        "search_files",
        "read_document",
        "extract_requirements",
        "detect_conflicts",
        "search_files",
        "read_document",
        "match_requirements",
    )
    cursor = -1
    selected = []
    for name in sequence:
        cursor = next(
            (index for index in range(cursor + 1, len(names)) if names[index] == name),
            -1,
        )
        if cursor < 0:
            raise ValueError(f"Material plan is missing or misorders {name}")
        selected.append(cursor)
    for step in steps:
        if (
            step["tool"]
            in {
                "read_document",
                "compare_versions",
                "extract_requirements",
                "detect_conflicts",
                "match_requirements",
            }
            and step["arguments"]
        ):
            raise ValueError(
                f"Material plan must resolve {step['tool']} from current Task results"
            )
        if step["tool"] == "search_files" and not step["arguments"]["query"].strip():
            raise ValueError("Material plan search query must be nonempty")
    collections = {"list_files", "search_files"}
    if any(
        steps[index]["tool"] in collections
        for index in range(selected[0] + 1, selected[3])
    ) or any(
        steps[index]["tool"] in collections
        for index in range(selected[4] + 1, selected[6])
    ):
        raise ValueError("Material reads must use their matching search results")
    if package:
        if names[-1] != "build_package":
            raise ValueError("Material package plan must end with build_package")
    elif "build_package" in names:
        raise ValueError("Material check did not request build_package")
    if "build_package" in names[:-1]:
        raise ValueError("build_package must be the final plan step")
    if any(name in {"create_folder", "copy_file", "move_file"} for name in names):
        raise ValueError("Material plan file changes require a frozen preview")


def validate_plan(
    payload: dict[str, Any],
    task_id: str,
    goal: str,
    *,
    enforce_material_workflow: bool = False,
) -> dict[str, Any]:
    """Normalize model output to the exact Plan and PlanStep contract fields."""
    if not task_id.strip() or not goal.strip():
        raise ValueError("task_id and goal are required")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("Plan must contain at least one step")
    steps = []
    for index, raw in enumerate(raw_steps, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"Step {index} must be an object")
        tool = raw.get("tool")
        if not isinstance(tool, str) or tool not in TOOL_RISKS:
            raise ValueError(f"Step {index} uses an unknown or forbidden tool")
        description = raw.get("description")
        arguments = raw.get("arguments")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Step {index} needs a description")
        if not isinstance(arguments, dict):
            raise ValueError(f"Step {index} arguments must be an object")
        validate_tool_arguments(tool, arguments, planning=True)
        steps.append(
            {
                "step_id": f"step_{index:03d}",
                "tool": tool,
                "description": description.strip(),
                "risk": TOOL_RISKS[tool],
                "status": "pending",
                "arguments": arguments,
            }
        )
    if enforce_material_workflow:
        _validate_material_sequence(steps, goal)
    return {"task_id": task_id, "goal": goal, "steps": steps}


def _generate_local(prompt: str, *, model: str, base_url: str) -> str:
    """Call the configured OpenAI-compatible planner endpoint."""
    import httpx

    try:
        import openai
    except ImportError as exc:
        raise RuntimeError(
            "Planner client dependency is missing. Install project dependencies "
            "or set FILEFORGE_AGENT_PLANNER_MODE=demo for E2E testing."
        ) from exc

    host = urlparse(base_url).hostname
    local = host in {"localhost", "127.0.0.1", "::1"}
    # Local model traffic must not be sent through a developer's HTTP proxy.
    with httpx.Client(trust_env=not local) as http_client:
        try:
            with openai.OpenAI(
                base_url=base_url,
                api_key=os.getenv("FILEFORGE_AGENT_PLANNER_API_KEY") or "ignored",
                http_client=http_client,
                timeout=15.0,
                max_retries=0,
            ) as client:
                request = dict(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                )
                if urlparse(base_url).hostname == "api.openai.com" and model.startswith(
                    ("gpt-4", "gpt-5")
                ):
                    request["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**request)
        except openai.APIError as exc:
            timeout_error = getattr(openai, "APITimeoutError", None)
            connection_error = getattr(openai, "APIConnectionError", None)
            status_error = getattr(openai, "APIStatusError", None)
            if isinstance(timeout_error, type) and isinstance(exc, timeout_error):
                detail = "request timed out"
            elif isinstance(connection_error, type) and isinstance(
                exc, connection_error
            ):
                detail = "connection failed"
            elif isinstance(status_error, type) and isinstance(exc, status_error):
                status = getattr(exc, "status_code", None)
                detail = f"HTTP {status}" if type(status) is int else "API status error"
            else:
                status = getattr(exc, "status_code", None)
                detail = f"HTTP {status}" if type(status) is int else "API error"
            raise RuntimeError(
                f"Planner model request failed ({detail}). Check the configured "
                "model, endpoint, and supported request parameters."
            ) from exc
    if not response.choices:
        raise ValueError("Planner returned empty response")
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise ValueError("Planner response was truncated")
    if getattr(choice.message, "refusal", None):
        raise ValueError("Planner refused to create a plan")
    if not choice.message.content or not choice.message.content.strip():
        raise ValueError("Planner returned empty response")
    return choice.message.content


def _demo_plan(task_id: str, workspace: Path) -> dict[str, Any]:
    """Exercise polling and approval without an LLM or source-file changes."""
    destination = workspace / f"Agent_Dev_Demo_{task_id.removeprefix('task_')}"
    return {
        "steps": [
            {
                "tool": "list_files",
                "description": "List workspace files",
                "arguments": {"workspace": str(workspace), "recursive": False},
            },
            {
                "tool": "create_folder",
                "description": "Create a demo folder after approval",
                "arguments": {"path": str(destination)},
            },
        ]
    }


def plan_task(
    task_id: str,
    user_goal: str,
    workspace: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    generate: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Generate a Plan; reject invalid or unsafe model output before execution."""
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Workspace is not a directory: {root}")
    if not user_goal.strip():
        raise ValueError("User goal is required")
    mode = os.getenv("FILEFORGE_AGENT_PLANNER_MODE", "llm").strip().lower()
    if mode not in {"llm", "demo"}:
        raise ValueError("FILEFORGE_AGENT_PLANNER_MODE must be llm or demo")
    if mode == "demo" and generate is None:
        return validate_plan(_demo_plan(task_id, root), task_id, user_goal)
    model = model or os.getenv("FILEFORGE_AGENT_PLANNER_MODEL", "qwen3-coder")
    base_url = base_url or os.getenv(
        "FILEFORGE_AGENT_PLANNER_BASE_URL", "http://localhost:11434/v1"
    )
    if not model.strip() or not base_url.strip():
        raise ValueError("Planner model and base URL must be nonempty")
    prompt = _PROMPT.format(
        tools=", ".join(_TOOL_ARGUMENTS), workspace=root, goal=user_goal
    )
    raw = (
        generate(prompt)
        if generate is not None
        else _generate_local(prompt, model=model, base_url=base_url)
    )
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Planner returned empty response")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Planner returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Planner response must be an object")
    return validate_plan(payload, task_id, user_goal, enforce_material_workflow=True)
