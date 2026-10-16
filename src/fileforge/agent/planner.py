"""Generate and validate a contract-shaped plan from a natural-language goal."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


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
    """Use the same local OpenAI-compatible server as FileForge classification."""
    import openai

    client = openai.OpenAI(base_url=base_url, api_key="ignored")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content or ""


def plan_task(
    task_id: str,
    user_goal: str,
    workspace: str,
    *,
    model: str = "qwen3-coder",
    base_url: str = "http://localhost:11434/v1",
    generate: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Generate a Plan; reject invalid or unsafe model output before execution."""
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Workspace is not a directory: {root}")
    if not user_goal.strip():
        raise ValueError("User goal is required")
    prompt = _PROMPT.format(
        tools=", ".join(TOOL_RISKS), workspace=root, goal=user_goal
    )
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
