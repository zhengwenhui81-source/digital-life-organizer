"""In-memory task lifecycle behind the agreed Agent HTTP contract."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from fileforge.agent.executor import (
    Resolver,
    ToolRouter,
    create_execution,
    execute,
    reject,
)
from fileforge.agent.planner import plan_task

_READABLE_EXTENSIONS = frozenset({".txt", ".pdf", ".docx", ".xlsx"})
_MAX_CANDIDATE_READS = 10


class TaskConflict(Exception):
    """The task is not in the state required for this request."""


class TaskService:
    """Keep task state in process memory, as permitted for the MVP."""

    def __init__(
        self,
        planner: Callable[[str, str, str], dict[str, Any]] = plan_task,
        router: ToolRouter | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self._planner = planner
        self._router = router or ToolRouter()
        self._resolver = resolver
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, user_goal: str, workspace: str) -> dict[str, Any]:
        if not user_goal.strip() or not workspace.strip():
            raise ValueError("user_goal and workspace are required")
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Workspace is not a directory: {root}")
        task = {
            "task_id": f"task_{uuid.uuid4().hex}",
            "user_goal": user_goal.strip(),
            "workspace": str(root),
            "status": "created",
        }
        with self._lock:
            self._tasks[task["task_id"]] = {
                "task": task,
                "execution": None,
                "preview_id": None,
                "error": None,
                "report": None,
                "approved_operations_verified": False,
            }
        return deepcopy(task)

    def _entry(self, task_id: str) -> dict[str, Any]:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError("Task not found") from exc

    def snapshot(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            entry = self._entry(task_id)
            state = entry["execution"]
            return deepcopy(
                {
                    "task": entry["task"],
                    "plan": state["plan"] if state else None,
                    "results": state["results"] if state else [],
                    "pending_operations": state["pending_operations"] if state else [],
                    "preview_id": entry["preview_id"],
                    "error": entry["error"],
                }
            )

    def run(self, task_id: str) -> None:
        with self._lock:
            entry = self._entry(task_id)
            if entry["task"]["status"] != "created":
                return
            entry["task"]["status"] = "planning"
            task = deepcopy(entry["task"])
        try:
            plan = self._planner(task["task_id"], task["user_goal"], task["workspace"])
            self._check_plan_paths(plan, Path(task["workspace"]))
            state = create_execution(plan)
            with self._lock:
                entry["execution"] = state
                entry["task"]["status"] = "executing"
            execute(
                state,
                self._router,
                resolver=self._scoped_resolver(Path(task["workspace"])),
            )
            self._finish(entry)
        except Exception as exc:
            with self._lock:
                entry["task"]["status"] = "failed"
                entry["error"] = str(exc) or type(exc).__name__
                if entry["execution"]:
                    entry["execution"]["pending_operations"] = []
                entry["preview_id"] = None

    @staticmethod
    def _check_plan_paths(plan: dict[str, Any], root: Path) -> None:
        for step in plan["steps"]:
            args = step["arguments"]
            paths = [
                (key, args.get(key))
                for key in ("workspace", "path", "source", "destination")
            ]
            if isinstance(args.get("documents"), list):
                paths.extend(
                    ("documents[].path", document.get("path"))
                    for document in args["documents"]
                    if isinstance(document, dict)
                )
            for key, value in paths:
                if value is None or value == "":
                    continue
                if not isinstance(value, str):
                    raise ValueError(f"{key} must be a path string")
                resolved = Path(value).expanduser().resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError(f"Tool path escapes workspace: {key}")

    def _scoped_resolver(self, root: Path) -> Resolver:
        def resolve(
            step: dict[str, Any], results: list[dict[str, Any]]
        ) -> dict[str, Any] | list[dict[str, Any]]:
            arguments = (
                self._resolver(step, results)
                if self._resolver is not None
                else step["arguments"]
            )
            if not isinstance(arguments, dict):
                raise ValueError("Resolver must return tool arguments")
            collection_index = next(
                (
                    index
                    for index in range(len(results) - 1, -1, -1)
                    if results[index].get("tool") in {"list_files", "search_files"}
                ),
                None,
            )
            candidates = None
            if collection_index is not None:
                collection = results[collection_index]
                if not collection.get("success"):
                    raise ValueError("Candidate collection failed")
                key = "files" if collection["tool"] == "list_files" else "matches"
                data = collection.get("data")
                if not isinstance(data, dict) or not isinstance(data.get(key), list):
                    raise ValueError("Candidate collection returned invalid file data")
                candidates = data[key]
            if step["tool"] == "read_document" and not arguments:
                if candidates is None:
                    raise ValueError(
                        "read_document path is unresolved; collect candidates first"
                    )
                paths = []
                for candidate in candidates:
                    if (
                        not isinstance(candidate, dict)
                        or not isinstance(candidate.get("path"), str)
                        or not candidate["path"].strip()
                    ):
                        raise ValueError(
                            "Candidate collection contains an invalid path"
                        )
                    path = candidate["path"]
                    if Path(path).suffix.casefold() in _READABLE_EXTENSIONS:
                        paths.append(path)
                if len(paths) > _MAX_CANDIDATE_READS:
                    raise ValueError(
                        f"Document batch exceeds {_MAX_CANDIDATE_READS} candidates"
                    )
                calls = [{"path": path} for path in paths]
                for call in calls:
                    self._check_plan_paths({"steps": [{"arguments": call}]}, root)
                return calls
            if any(
                result.get("tool") == "read_document" and not result.get("success")
                for result in results
            ):
                raise ValueError("A document read failed; analysis cannot continue")
            if (
                step["tool"]
                in {
                    "compare_versions",
                    "detect_conflicts",
                    "extract_requirements",
                }
                and arguments.get("documents", []) == []
            ):
                read_documents = [
                    result["data"]["document"]
                    for result in results[
                        collection_index + 1 if collection_index is not None else 0 :
                    ]
                    if result.get("tool") == "read_document"
                    and result.get("success")
                    and isinstance(result.get("data"), dict)
                    and isinstance(result["data"].get("document"), dict)
                ]
                if not read_documents and not (
                    candidates is not None
                    and all(
                        isinstance(candidate, dict)
                        and isinstance(candidate.get("path"), str)
                        and Path(candidate["path"]).suffix.casefold()
                        not in _READABLE_EXTENSIONS
                        for candidate in candidates
                    )
                ):
                    raise ValueError(
                        f"{step['tool']} documents are unresolved; read candidates "
                        "or establish an empty candidate collection first"
                    )
                arguments = {**arguments, "documents": read_documents}
            self._check_plan_paths({"steps": [{"arguments": arguments}]}, root)
            if step["tool"] in {
                "compare_versions",
                "detect_conflicts",
                "extract_requirements",
            }:
                documents = arguments.get("documents")
                if isinstance(documents, list):
                    if not documents and not any(
                        result.get("success")
                        and result.get("tool")
                        in {"list_files", "search_files", "read_document"}
                        for result in results
                    ):
                        raise ValueError(
                            "Empty documents require completed candidate collection"
                        )
                    read_documents = [
                        result["data"]["document"]
                        for result in results
                        if result.get("tool") == "read_document"
                        and result.get("success")
                        and isinstance(result.get("data"), dict)
                        and isinstance(result["data"].get("document"), dict)
                    ]
                    if any(document not in read_documents for document in documents):
                        raise ValueError(
                            "Analysis documents must come from successful read_document"
                        )
            return arguments

        return resolve

    @staticmethod
    def _verify_approved(operations: list[dict[str, Any]]) -> dict[str, Any]:
        """Check the frozen approved paths after successful tool execution."""
        checks = []
        for step in operations:
            tool, args = step["tool"], step["arguments"]
            if tool == "create_folder":
                target = Path(args["path"])
                passed = target.is_dir() and not target.is_symlink()
            elif tool in {"copy_file", "move_file"}:
                source, target = Path(args["source"]), Path(args["destination"])
                passed = target.is_file() and not target.is_symlink()
                if tool == "copy_file":
                    if not source.is_file() or not passed:
                        passed = False
                    else:

                        def digest(path: Path) -> bytes:
                            hash_value = hashlib.sha256()
                            with path.open("rb") as stream:
                                for chunk in iter(
                                    lambda: stream.read(1024 * 1024), b""
                                ):
                                    hash_value.update(chunk)
                            return hash_value.digest()

                        try:
                            passed = digest(source) == digest(target)
                        except OSError:
                            passed = False
                else:
                    passed = passed and not source.exists()
            else:
                raise ValueError(f"Cannot verify approved operation: {tool}")
            checks.append({"path": str(target), "kind": tool, "passed": passed})
        passed = all(check["passed"] for check in checks)
        return {
            "success": passed,
            "tool": "verify_result",
            "data": {"checks": checks, "passed": True} if passed else None,
            "message": (
                "Approved file operations verified" if passed else "Verification failed"
            ),
            "error": (
                None
                if passed
                else "Approved file operation result differs from the frozen preview"
            ),
        }

    def _finish(
        self,
        entry: dict[str, Any],
        approved_operations: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._lock:
            state = entry["execution"]
            if state["status"] == "completed" and approved_operations:
                verification = self._verify_approved(approved_operations)
                state["results"].append(verification)
                if not verification["success"]:
                    state["status"] = "failed"
                else:
                    entry["approved_operations_verified"] = True
            status = state["status"]
            entry["task"]["status"] = status
            entry["preview_id"] = None
            if status == "awaiting_approval":
                self._validate_preview(entry)
                payload = json.dumps(
                    {
                        "task_id": state["task_id"],
                        "operations": state["pending_operations"],
                        "nonce": secrets.token_hex(16),
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                )
                entry["preview_id"] = (
                    "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
                )
            elif status == "failed":
                last = state["results"][-1] if state["results"] else None
                entry["error"] = (last or {}).get("error") or "Task execution failed"
            elif status == "completed":
                entry["task"]["status"] = "verifying"
                entry["report"] = self._report(entry)
                entry["task"]["status"] = "completed"

    def _validate_preview(self, entry: dict[str, Any]) -> None:
        root = Path(entry["task"]["workspace"])
        pending = entry["execution"]["pending_operations"]
        required = {
            "create_folder": ("path",),
            "copy_file": ("source", "destination"),
            "move_file": ("source", "destination"),
        }
        for step in pending:
            if step["tool"] not in required:
                raise ValueError(f"Unavailable file operation: {step['tool']}")
            args = step["arguments"]
            for key in required[step["tool"]]:
                if not isinstance(args.get(key), str) or not args[key].strip():
                    raise ValueError(f"Unresolved file operation: {key}")
            self._check_plan_paths({"steps": [step]}, root)

    @staticmethod
    def _report(entry: dict[str, Any]) -> dict[str, Any]:
        state = entry["execution"]
        found = []
        version_groups = []
        conflicts = []
        operations = []
        for result in state["results"]:
            if result["tool"] == "list_files" and result["success"]:
                found.extend(result["data"].get("files", []))
            if result["tool"] == "compare_versions" and result["success"]:
                version_groups.extend(result["data"].get("groups", []))
            if result["tool"] == "detect_conflicts" and result["success"]:
                conflicts.extend(result["data"].get("conflicts", []))
            if result["tool"] in {"create_folder", "copy_file", "move_file"}:
                operations.append(result)
        return {
            "task_id": entry["task"]["task_id"],
            "status": "completed",
            "found_files": found,
            "version_groups": version_groups,
            "conflicts": conflicts,
            "missing_items": [],
            "operations": operations,
            "package_path": "",
            "summary": (
                "Completed and verified approved file operations"
                if entry["approved_operations_verified"]
                else "Completed the available plan steps"
            ),
        }

    def decide(self, task_id: str, preview_id: str, *, approve: bool) -> dict[str, Any]:
        with self._lock:
            entry = self._entry(task_id)
            if (
                entry["task"]["status"] != "awaiting_approval"
                or not preview_id
                or preview_id != entry["preview_id"]
            ):
                raise TaskConflict(
                    "Approval preview is stale or task is not awaiting approval"
                )
            entry["preview_id"] = None  # consume before running any file operation
            entry["task"]["status"] = "executing" if approve else "failed"
            state = entry["execution"]
            if not approve:
                reject(state)
                entry["error"] = "User rejected pending operations"
                return self.snapshot(task_id)
        try:
            self._validate_preview(entry)
            approved_operations = deepcopy(state["pending_operations"])
            execute(
                state,
                self._router,
                approve_all=True,
                resolver=self._scoped_resolver(Path(entry["task"]["workspace"])),
            )
            self._finish(entry, approved_operations)
        except Exception as exc:
            with self._lock:
                state["status"] = "failed"
                state["pending_operations"] = []
                entry["task"]["status"] = "failed"
                entry["error"] = str(exc) or type(exc).__name__
        return self.snapshot(task_id)

    def report(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            entry = self._entry(task_id)
            if entry["task"]["status"] != "completed" or entry["report"] is None:
                raise TaskConflict("Report is not available")
            return deepcopy(entry["report"])
