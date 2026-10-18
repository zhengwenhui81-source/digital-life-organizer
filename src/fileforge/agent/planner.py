"""Generate and validate a contract-shaped plan from a natural-language goal."""

from __future__ import annotations

import json
import os
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
    "verify_result": "low",
    "create_folder": "medium",
    "copy_file": "medium",
    "move_file": "medium",
    "build_package": "medium",
}

_PROMPT = """Plan a local file task. Respond with JSON only, as an object with a
"steps" array. Each step must contain "tool", "description", and "arguments".
Use only these tool names: {tools}.
Read and analysis steps should precede file changes. Include only steps that
serve the goal. Do not invent filenames, file contents, or results. When an
argument depends on a previous result, use an empty object or list placeholder.
To analyze unknown workspace documents, collect candidates with list_files or
search_files, then use read_document with empty arguments to read each supported
candidate. A following compare_versions with empty arguments compares documents
read after that collection. A failed read stops the task.
Never plan deletion or overwrite. File-changing steps will require user approval.
Workspace: {workspace}
Goal: {goal}
"""


def validate_plan(payload: dict[str, Any], task_id: str, goal: str) -> dict[str, Any]:
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
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
        except openai.APIError as exc:
            status = getattr(exc, "status_code", None)
            detail = f"HTTP {status}" if status else "connection failed"
            raise RuntimeError(
                f"Planner model unavailable ({detail}; model={model}; "
                f"base_url={base_url}). Configure FILEFORGE_AGENT_PLANNER_MODEL "
                "and FILEFORGE_AGENT_PLANNER_BASE_URL, or set "
                "FILEFORGE_AGENT_PLANNER_MODE=demo for E2E testing."
            ) from exc
    return response.choices[0].message.content or ""


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
    prompt = _PROMPT.format(tools=", ".join(TOOL_RISKS), workspace=root, goal=user_goal)
    raw = (
        generate(prompt)
        if generate is not None
        else _generate_local(prompt, model=model, base_url=base_url)
    )
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Planner returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Planner response must be an object")
    return validate_plan(payload, task_id, user_goal)
