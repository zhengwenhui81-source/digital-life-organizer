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
from fileforge.agent.package_evidence import (
    _same_document,
    collect_package_read_results,
    current_package_analysis,
    revalidate_documents,
)
from fileforge.agent.package_execution import execute_package
from fileforge.agent.package_preview import freeze_package_preview
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
                "package_approval": None,
                "package_execution": None,
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
                    "package_execution": entry["package_execution"],
                }
            )

    def _package_preflight(self, task_id: str) -> dict[str, Any]:
        """Authenticate and revalidate current analysis before Package planning."""
        with self._lock:
            entry = self._entry(task_id)
            state = entry["execution"]
            if (
                entry["task"]["status"] != "completed"
                or state is None
                or state["status"] != "completed"
                or entry["package_approval"] is not None
                or entry["package_execution"] is not None
            ):
                raise TaskConflict("Package analysis is not completed")
            try:
                reads = collect_package_read_results(state, task_id=task_id)
                analysis = current_package_analysis(state, task_id=task_id)
                checked = revalidate_documents(entry["task"]["workspace"], reads)
            except Exception as exc:
                state["status"] = "failed"
                state["pending_operations"] = []
                entry["task"]["status"] = "failed"
                entry["error"] = str(exc) or type(exc).__name__
                entry["report"] = None
                entry["preview_id"] = None
                entry["package_approval"] = None
                raise
            return {"analysis": analysis, "checked": checked}

    def prepare_package(
        self,
        task_id: str,
        selected_files: list[dict[str, Any]],
        destination: str,
    ) -> dict[str, Any]:
        """Plan a Package from this Task's authenticated analysis, without writes.

        This remains an internal orchestration entry; it does not add a
        post-analysis HTTP selection endpoint. The same preview is required
        before the composite builder can execute any Package writes.
        """
        from fileforge.package import plan_package

        evidence = self._package_preflight(task_id)
        with self._lock:
            entry = self._entry(task_id)
            task = deepcopy(entry["task"])
            task.pop("status")
            state = entry["execution"]
            if entry["task"]["status"] != "completed":
                raise TaskConflict("Package analysis is no longer current")
            try:
                result = plan_package(
                    task=task,
                    selected_files=selected_files,
                    destination=destination,
                    analysis=evidence["analysis"],
                )
            except Exception as exc:
                result = {
                    "success": False,
                    "tool": "plan_package",
                    "data": None,
                    "message": "Package planning failed",
                    "error": str(exc) or type(exc).__name__,
                }
            try:
                plan, bindings, operations = freeze_package_preview(
                    task, evidence["analysis"], evidence["checked"], result
                )
            except Exception as exc:
                failure = (
                    result
                    if (
                        type(result) is dict
                        and result.get("tool") == "plan_package"
                        and result.get("success") is False
                        and result.get("data") is None
                        and type(result.get("message")) is str
                        and type(result.get("error")) is str
                    )
                    else {
                        "success": False,
                        "tool": "plan_package",
                        "data": None,
                        "message": "Package preview validation failed",
                        "error": str(exc) or type(exc).__name__,
                    }
                )
                self._record_package_plan(
                    state,
                    task,
                    selected_files,
                    destination,
                    evidence["analysis"],
                    failure,
                )
                state["status"] = "failed"
                entry["task"]["status"] = "failed"
                entry["error"] = failure["error"]
                entry["report"] = None
                entry["preview_id"] = None
                return self.snapshot(task_id)
            self._record_package_plan(
                state, task, selected_files, destination, evidence["analysis"], result
            )
            payload = json.dumps(
                {
                    "task_id": task_id,
                    "plan_id": plan["plan_id"],
                    "plan_sha256": result["data"]["plan_sha256"],
                    "plan": plan,
                    "operations": operations,
                    "approval_state": "awaiting_approval",
                    "nonce": secrets.token_hex(16),
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            preview_id = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
            entry["package_approval"] = {
                "preview_id": preview_id,
                "plan_id": plan["plan_id"],
                "plan_sha256": result["data"]["plan_sha256"],
                "plan": plan,
                "checked": deepcopy(evidence["checked"]),
                "bindings": bindings,
                "missing": deepcopy(plan["missing"]),
                "unresolved": deepcopy(plan["unresolved"]),
            }
            state["status"] = "awaiting_approval"
            state["pending_operations"] = operations
            entry["task"]["status"] = "awaiting_approval"
            entry["preview_id"] = preview_id
            entry["error"] = None
            entry["report"] = None
            return self.snapshot(task_id)

    @staticmethod
    def _record_package_plan(
        state: dict[str, Any],
        task: dict[str, Any],
        selected_files: list[dict[str, Any]],
        destination: str,
        analysis: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Append one low-risk D result with its actual task-scoped call inputs."""
        step_id = f"step_{len(state['plan']['steps']) + 1:03d}"
        state["plan"]["steps"].append(
            {
                "step_id": step_id,
                "tool": "plan_package",
                "description": "Prepare a read-only Package preview",
                "risk": "low",
                "status": "completed" if result["success"] else "failed",
                "arguments": {},
            }
        )
        result_index = len(state["results"])
        state["results"].append(deepcopy(result))
        state["result_calls"].append(
            {
                "result_index": result_index,
                "step_id": step_id,
                "tool": "plan_package",
                "arguments": {
                    "task": deepcopy(task),
                    "selected_files": deepcopy(selected_files),
                    "destination": destination,
                    "analysis": deepcopy(analysis),
                },
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
            package_steps = [
                index
                for index, step in enumerate(plan["steps"])
                if step["tool"] == "build_package"
            ]
            wants_package = bool(package_steps)
            if wants_package:
                if (
                    package_steps != [len(plan["steps"]) - 1]
                    or len(plan["steps"]) < 2
                    or plan["steps"][-1]["arguments"] != {}
                    or any(step["risk"] != "low" for step in plan["steps"][:-1])
                ):
                    raise ValueError(
                        "Package request must follow completed read-only analysis"
                    )
                plan = deepcopy(plan)
                plan["steps"].pop()
            self._check_plan_paths(plan, Path(task["workspace"]))
            state = create_execution(plan)
            with self._lock:
                entry["execution"] = state
                entry["task"]["status"] = "executing"
            execute(
                state,
                self._router,
                resolver=self._scoped_resolver(
                    Path(task["workspace"]), state["plan"]["steps"]
                ),
            )
            self._finish(entry)
            if wants_package and entry["task"]["status"] == "completed":
                selected, destination = self._propose_package(task_id)
                self.prepare_package(task_id, selected, destination)
        except Exception as exc:
            with self._lock:
                entry["task"]["status"] = "failed"
                entry["error"] = str(exc) or type(exc).__name__
                if entry["execution"]:
                    entry["execution"]["status"] = "failed"
                    for step in entry["execution"]["plan"]["steps"]:
                        if step["status"] in {"pending", "running"}:
                            step["status"] = "failed"
                            break
                    entry["execution"]["pending_operations"] = []
                entry["preview_id"] = None
                entry["report"] = None

    def _propose_package(self, task_id: str) -> tuple[list[dict], str]:
        """Suggest only unique filename candidates from this Task's matching."""
        with self._lock:
            entry = self._entry(task_id)
            if entry["task"]["status"] != "completed":
                raise TaskConflict("Package analysis is not completed")
            matches = [
                result
                for result in entry["execution"]["results"]
                if result.get("tool") == "match_requirements"
            ]
            if not matches or matches[-1].get("success") is not True:
                raise ValueError(
                    "Package needs successful current requirement matching"
                )
            data = matches[-1].get("data")
            groups = data.get("matched") if type(data) is dict else None
            if type(groups) is not list:
                raise ValueError("Package matching returned invalid candidates")
            selected: list[dict] = []
            by_id: dict[str, dict] = {}
            for group in groups:
                if type(group) is not dict or type(group.get("documents")) is not list:
                    raise ValueError("Package matching returned invalid candidates")
                documents = group["documents"]
                if len(documents) != 1:
                    continue  # Ambiguous candidates are never chosen silently.
                requirement = group.get("requirement")
                source = documents[0]
                if (
                    type(requirement) is not str
                    or not requirement.strip()
                    or type(source) is not dict
                    or any(
                        type(source.get(key)) is not str or not source[key]
                        for key in ("file_id", "path", "filename")
                    )
                ):
                    raise ValueError(
                        "Package matching returned invalid source references"
                    )
                file_id = source["file_id"]
                reference = {
                    key: source[key] for key in ("file_id", "path", "filename")
                }
                prior = by_id.get(file_id)
                if prior is not None:
                    if prior["source"] != reference:
                        raise ValueError(
                            "Package matching has contradictory file identity"
                        )
                    if requirement not in prior["requirements"]:
                        prior["requirements"].append(requirement)
                    continue
                proposed = {
                    "source": reference,
                    "requirements": [requirement],
                    "reason": "当前任务的唯一文件名候选；仍待用户在预览中确认",
                }
                selected.append(proposed)
                by_id[file_id] = proposed
            if not selected:
                raise ValueError(
                    "No unambiguous material candidate can be proposed for Package"
                )
            root = Path(entry["task"]["workspace"])
            destination = str(root / f"package_{task_id}")
            return selected, destination

    @staticmethod
    def _check_plan_paths(plan: dict[str, Any], root: Path) -> None:
        for step in plan["steps"]:
            args = step["arguments"]
            paths = [
                (key, args.get(key))
                for key in ("workspace", "path", "source", "destination")
            ]
            for field in ("documents", "candidate_documents"):
                if isinstance(args.get(field), list):
                    paths.extend(
                        (f"{field}[].path", document.get("path"))
                        for document in args[field]
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

    def _scoped_resolver(
        self, root: Path, plan_steps: list[dict[str, Any]]
    ) -> Resolver:
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
                if not paths:
                    if not candidates:
                        position = next(
                            index
                            for index, planned in enumerate(plan_steps)
                            if planned["step_id"] == step["step_id"]
                        )
                        if (
                            position + 1 < len(plan_steps)
                            and plan_steps[position + 1]["tool"] == "match_requirements"
                            and any(
                                result.get("tool") == "extract_requirements"
                                and result.get("success")
                                for result in results
                            )
                        ):
                            # No material candidates were collected. The read
                            # step is skipped; matching can report missing names.
                            return []
                        raise ValueError(
                            "No matching document found; read_document was not "
                            "called and analysis was not performed"
                        )
                    raise ValueError(
                        "No readable document found among the collected candidates; "
                        "read_document was not called and analysis was not performed"
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
            if step["tool"] == "extract_requirements" and not any(
                result.get("tool") == "read_document" and result.get("success")
                for result in results[
                    collection_index + 1 if collection_index is not None else 0 :
                ]
            ):
                raise ValueError(
                    "No document was read; requirements were not extracted"
                )
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
            if step["tool"] == "match_requirements":
                extraction_index = next(
                    (
                        index
                        for index in range(len(results) - 1, -1, -1)
                        if results[index].get("tool") == "extract_requirements"
                    ),
                    None,
                )
                if extraction_index is None:
                    raise ValueError(
                        "match_requirements requires a completed requirement extraction"
                    )
                extraction = results[extraction_index]
                data = extraction.get("data")
                if not extraction.get("success") or not isinstance(data, dict):
                    raise ValueError(
                        "Requirement extraction failed; matching cannot run"
                    )
                required = data.get("required_documents")
                if not isinstance(required, list) or not all(
                    type(name) is str for name in required
                ):
                    raise ValueError("Requirement extraction returned invalid data")
                if arguments.get("required_documents") not in (None, [], required):
                    raise ValueError(
                        "Matching requirements must come from requirement extraction"
                    )
                candidate_collection = (
                    candidates
                    if collection_index is not None
                    and collection_index > extraction_index
                    else None
                )
                start = (
                    collection_index + 1
                    if candidate_collection is not None
                    else extraction_index + 1
                )
                candidate_reads = [
                    result
                    for result in results[start:]
                    if result.get("tool") == "read_document" and result.get("success")
                ]
                if any(
                    not isinstance(result.get("data"), dict)
                    or not isinstance(result["data"].get("document"), dict)
                    for result in candidate_reads
                ):
                    raise ValueError("Candidate read returned invalid Document data")
                notice_collection_index = next(
                    (
                        index
                        for index in range(extraction_index - 1, -1, -1)
                        if results[index].get("tool") in {"list_files", "search_files"}
                    ),
                    None,
                )
                notice_start = (
                    notice_collection_index + 1
                    if notice_collection_index is not None
                    else 0
                )
                notice_ids = {
                    result["data"]["document"].get("file_id")
                    for result in results[notice_start:extraction_index]
                    if result.get("tool") == "read_document"
                    and result.get("success")
                    and isinstance(result.get("data"), dict)
                    and isinstance(result["data"].get("document"), dict)
                }
                documents = [
                    result["data"]["document"]
                    for result in candidate_reads
                    if result["data"]["document"].get("file_id") not in notice_ids
                ]
                if (
                    not documents
                    and candidate_collection != []
                    and (required or candidate_collection is not None)
                ):
                    raise ValueError(
                        "Candidate documents are unresolved; collect and read "
                        "materials after requirement extraction"
                    )
                supplied_candidates = arguments.get("candidate_documents")
                if supplied_candidates not in (None, []) and (
                    type(supplied_candidates) is not list
                    or len(supplied_candidates) != len(documents)
                    or any(
                        not _same_document(supplied, actual)
                        for supplied, actual in zip(supplied_candidates, documents)
                    )
                ):
                    raise ValueError(
                        "Matching candidates must come from successful read_document"
                    )
                arguments = {
                    "required_documents": required,
                    "candidate_documents": documents,
                }
            self._check_plan_paths({"steps": [{"arguments": arguments}]}, root)
            if step["tool"] in {
                "compare_versions",
                "detect_conflicts",
                "extract_requirements",
            }:
                documents = arguments.get("documents")
                if isinstance(documents, list):
                    if step["tool"] == "extract_requirements" and not documents:
                        raise ValueError(
                            "No document was read; requirements were not extracted"
                        )
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
                    if any(
                        not any(
                            _same_document(document, prior) for prior in read_documents
                        )
                        for document in documents
                    ):
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
        found_paths = set()
        version_groups = []
        conflicts = []
        operations = []
        empty_requirements = False
        matching = None
        for result in state["results"]:
            if result["success"] and result["tool"] in {"list_files", "search_files"}:
                key = "files" if result["tool"] == "list_files" else "matches"
                for file in result["data"].get(key, []):
                    if not isinstance(file, dict) or not isinstance(
                        file.get("path"), str
                    ):
                        raise ValueError("File collection returned invalid record")
                    if file["path"] not in found_paths:
                        found_paths.add(file["path"])
                        found.append(file)
            if result["tool"] == "compare_versions" and result["success"]:
                version_groups.extend(result["data"].get("groups", []))
            if result["tool"] == "detect_conflicts" and result["success"]:
                conflicts.extend(result["data"].get("conflicts", []))
            if result["tool"] == "extract_requirements" and result["success"]:
                empty_requirements = not result["data"].get("required_documents", [])
            if result["tool"] == "match_requirements":
                matching = result
            if result["tool"] in {"create_folder", "copy_file", "move_file"}:
                operations.append(result)
        return {
            "task_id": entry["task"]["task_id"],
            "status": "completed",
            "found_files": found,
            "version_groups": version_groups,
            "conflicts": conflicts,
            "missing_items": (
                matching["data"]["missing"]
                if matching is not None and matching["success"]
                else []
            ),
            "operations": operations,
            "package_path": "",
            "summary": (
                "Completed and verified approved file operations"
                if entry["approved_operations_verified"]
                else (
                    "Analysis completed; requirement extraction returned no "
                    "material names. Whether materials are required remains "
                    "unverified; no package was built."
                    if empty_requirements
                    else (
                        "Filename candidate matching completed; materials not reviewed"
                        if matching is not None
                        else "Completed the available plan steps"
                    )
                )
            ),
        }

    def decide(
        self,
        task_id: str,
        preview_id: str,
        *,
        approve: bool,
        accept_incomplete: bool = False,
    ) -> dict[str, Any]:
        package_execution = None
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
            if type(accept_incomplete) is not bool:
                raise TaskConflict("accept_incomplete must be a boolean")
            if not approve and accept_incomplete:
                raise TaskConflict("Rejection cannot accept Package risks")
            package = entry["package_approval"]
            if approve and package is not None:
                if (
                    type(package) is not dict
                    or package.get("preview_id") != preview_id
                    or type(package.get("plan_id")) is not str
                    or not package["plan_id"]
                    or type(package.get("plan_sha256")) is not str
                    or not package["plan_sha256"]
                    or type(package.get("missing")) is not list
                    or type(package.get("unresolved")) is not list
                ):
                    raise TaskConflict("Package plan is not bound to this preview")
                if (
                    package["missing"] or package["unresolved"]
                ) and not accept_incomplete:
                    raise TaskConflict(
                        "Package has missing or unresolved items; accept this "
                        "preview's specific risks before approval"
                    )
                if (
                    type(package.get("plan")) is not dict
                    or type(package.get("checked")) is not dict
                ):
                    raise TaskConflict("Package execution is not available")
                results = entry["execution"]["results"]
                plan_result = results[-1] if results else None
                plan_data = (
                    plan_result.get("data") if type(plan_result) is dict else None
                )
                plan = package["plan"]
                canonical = json.dumps(
                    {key: value for key, value in plan.items() if key != "plan_id"},
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                current_digest = (
                    "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                )
                if (
                    type(plan_data) is not dict
                    or plan_result.get("tool") != "plan_package"
                    or plan_result.get("success") is not True
                    or plan_data.get("plan_sha256") != package["plan_sha256"]
                    or not _same_document(plan_data.get("plan"), plan)
                    or plan.get("plan_id") != package["plan_id"]
                    or current_digest != package["plan_sha256"]
                    or not _same_document(plan.get("missing"), package["missing"])
                    or not _same_document(plan.get("unresolved"), package["unresolved"])
                    or not _same_document(
                        self._package_steps(package),
                        entry["execution"]["pending_operations"],
                    )
                ):
                    raise TaskConflict("Package plan is not bound to this preview")
                package_execution = deepcopy(package)
            entry["preview_id"] = None  # consume before running any file operation
            entry["task"]["status"] = "executing" if approve else "failed"
            state = entry["execution"]
            if not approve:
                reject(state)
                entry["error"] = "User rejected pending operations"
                return self.snapshot(task_id)
            if package_execution is not None:
                state["status"] = "executing"
                state["pending_operations"] = []
                entry["package_execution"] = {
                    "plan_id": package_execution["plan_id"],
                    "plan_sha256": package_execution["plan_sha256"],
                    "operation_results": [],
                    "cleanup_results": [],
                    "final_result_index": None,
                }
        if package_execution is not None:
            return self._run_package(task_id, package_execution)
        try:
            self._validate_preview(entry)
            approved_operations = deepcopy(state["pending_operations"])
            execute(
                state,
                self._router,
                approve_all=True,
                resolver=self._scoped_resolver(
                    Path(entry["task"]["workspace"]), state["plan"]["steps"]
                ),
            )
            self._finish(entry, approved_operations)
        except Exception as exc:
            with self._lock:
                state["status"] = "failed"
                state["pending_operations"] = []
                entry["task"]["status"] = "failed"
                entry["error"] = str(exc) or type(exc).__name__
        return self.snapshot(task_id)

    def _run_package(self, task_id: str, frozen: dict[str, Any]) -> dict[str, Any]:
        """Commit one approved composite Package and retain every child result."""
        with self._lock:
            entry = self._entry(task_id)
            state = entry["execution"]
            preview = {step["step_id"]: step for step in self._package_steps(frozen)}

        def append(step_id: str, result: dict[str, Any]) -> int:
            with self._lock:
                step = deepcopy(preview[step_id])
                step["status"] = "completed" if result["success"] else "failed"
                state["plan"]["steps"].append(step)
                index = len(state["results"])
                state["results"].append(deepcopy(result))
                state["result_calls"].append(
                    {
                        "result_index": index,
                        "step_id": step_id,
                        "tool": result["tool"],
                        "arguments": deepcopy(step["arguments"]),
                    }
                )
                entry["package_execution"]["operation_results"].append(
                    {"step_id": step_id, "result_index": index}
                )
                return index

        try:
            final, cleanup = execute_package(
                frozen["plan"],
                frozen["plan_sha256"],
                frozen["checked"],
                frozen["bindings"],
                append,
            )
        except Exception as exc:
            final, cleanup = (
                {
                    "success": False,
                    "tool": "build_package",
                    "data": None,
                    "message": "build_package failed",
                    "error": str(exc) or type(exc).__name__,
                },
                [],
            )
        with self._lock:
            entry = self._entry(task_id)
            state = entry["execution"]
            entry["package_execution"]["cleanup_results"] = cleanup
            final_index = len(state["results"])
            state["results"].append(final)
            build_step = {
                "step_id": f"step_{len(state['plan']['steps']) + 1:03d}",
                "tool": "build_package",
                "description": "Execute the approved frozen Package",
                "risk": "medium",
                "status": "completed" if final["success"] else "failed",
                "arguments": {
                    "task_id": task_id,
                    "plan_id": frozen["plan_id"],
                    "plan_sha256": frozen["plan_sha256"],
                },
            }
            state["plan"]["steps"].append(build_step)
            state["result_calls"].append(
                {
                    "result_index": final_index,
                    "step_id": build_step["step_id"],
                    "tool": "build_package",
                    "arguments": deepcopy(build_step["arguments"]),
                }
            )
            entry["package_execution"]["final_result_index"] = final_index
            state["status"] = "completed" if final["success"] else "failed"
            entry["task"]["status"] = state["status"]
            if final["success"]:
                try:
                    entry["report"] = self._package_report(entry, frozen)
                    entry["error"] = None
                except Exception as exc:
                    failure = {
                        "success": False,
                        "tool": "build_package",
                        "data": None,
                        "message": "build_package failed",
                        "error": str(exc) or type(exc).__name__,
                    }
                    state["results"][final_index] = failure
                    build_step["status"] = "failed"
                    state["status"] = "failed"
                    entry["task"]["status"] = "failed"
                    entry["error"] = failure["error"]
                    entry["report"] = None
            else:
                entry["error"] = final["error"]
                entry["report"] = None
            return self.snapshot(task_id)

    @staticmethod
    def _package_steps(frozen: dict[str, Any]) -> list[dict[str, Any]]:
        plan = frozen["plan"]
        steps = []
        for index, descriptor in enumerate(plan["operations"]):
            kind = descriptor["kind"]
            if kind == "create_directory":
                tool, args, risk = (
                    "create_folder",
                    {"path": plan["destination"]},
                    "medium",
                )
            elif kind == "copy":
                item = plan["selected_files"][descriptor["selected_file_index"]]
                tool = "copy_file"
                args = {"source": item["source"]["path"], "destination": item["target"]}
                risk = "medium"
            elif kind == "write_report":
                tool = "write_package_report"
                args = {
                    "task_id": plan["task"]["task_id"],
                    "plan_id": plan["plan_id"],
                    "plan_sha256": frozen["plan_sha256"],
                }
                risk = "medium"
            else:
                tool = "verify_result"
                args = {
                    "task_id": plan["task"]["task_id"],
                    "workspace": plan["task"]["workspace"],
                    "expected": plan["verification_targets"],
                }
                risk = "low"
            steps.append(
                {
                    "step_id": descriptor["step_id"],
                    "tool": tool,
                    "description": f"Package {kind}",
                    "risk": risk,
                    "status": "awaiting_approval",
                    "arguments": args,
                }
            )
        return steps

    def _package_report(
        self, entry: dict[str, Any], frozen: dict[str, Any]
    ) -> dict[str, Any]:
        mapping = entry["package_execution"]
        state = entry["execution"]
        plan = frozen["plan"]
        final_index = mapping["final_result_index"]
        if (
            mapping["plan_id"] != plan["plan_id"]
            or mapping["plan_sha256"] != frozen["plan_sha256"]
            or type(final_index) is not int
            or final_index != len(state["results"]) - 1
        ):
            raise ValueError("Package report has no bound final result")
        final = state["results"][final_index]
        if (
            not final["success"]
            or final["tool"] != "build_package"
            or final["data"]["plan_id"] != plan["plan_id"]
            or final["data"]["plan_sha256"] != frozen["plan_sha256"]
            or final["data"]["package_path"] != plan["destination"]
            or final["data"]["report_path"] != plan["report"]["path"]
            or final["data"]["generated_files"]
            != [
                *(item["target"] for item in plan["selected_files"]),
                plan["report"]["path"],
            ]
        ):
            raise ValueError("Package report has no verified current execution")
        verify_index = final["data"]["verification_result_index"]
        descriptors = plan["operations"]
        recorded = mapping["operation_results"]
        if (
            type(verify_index) is not int
            or verify_index < 0
            or verify_index >= final_index
            or len(recorded) != len(descriptors)
            or recorded[-1]
            != {
                "step_id": descriptors[-1]["step_id"],
                "result_index": verify_index,
            }
            or state["results"][verify_index].get("tool") != "verify_result"
            or state["results"][verify_index].get("success") is not True
            or state["results"][verify_index].get("data", {}).get("passed") is not True
        ):
            raise ValueError("Package verification is not complete")
        checks = state["results"][verify_index]["data"].get("checks")
        expected_checks = [
            (plan["task"]["workspace"], "source-snapshot"),
            *((item["target"], "material-digest") for item in plan["selected_files"]),
            (plan["report"]["path"], "report-digest"),
            (plan["destination"], "file-set"),
        ]
        if (
            type(checks) is not list
            or len(checks) != len(expected_checks)
            or any(
                type(check) is not dict
                or check.get("path") != expected_path
                or check.get("kind") != expected_kind
                or check.get("passed") is not True
                for check, (expected_path, expected_kind) in zip(
                    checks, expected_checks
                )
            )
        ):
            raise ValueError("Package verification checks are incomplete")
        writes = []
        prior_index = -1
        for descriptor, link in zip(descriptors, recorded):
            index = link.get("result_index") if type(link) is dict else None
            expected_tool = {
                "create_directory": "create_folder",
                "copy": "copy_file",
                "write_report": "write_package_report",
                "verify": "verify_result",
            }.get(descriptor["kind"])
            if (
                type(link) is not dict
                or link.get("step_id") != descriptor["step_id"]
                or type(index) is not int
                or index <= prior_index
                or index >= final_index
                or state["results"][index].get("tool") != expected_tool
                or state["results"][index].get("success") is not True
            ):
                raise ValueError("Package operation results differ from frozen plan")
            prior_index = index
            if descriptor["kind"] != "verify":
                writes.append(deepcopy(state["results"][index]))
        report = self._report(entry)
        report["package_path"] = plan["destination"]
        report["operations"] = writes
        report["missing_items"] = deepcopy(plan["missing"])
        report["package_unresolved"] = {
            "plan_id": plan["plan_id"],
            "plan_sha256": frozen["plan_sha256"],
            "items": deepcopy(plan["unresolved"]),
        }
        conflict = plan["analysis"]["detect_conflicts"]
        report["conflicts"] = (
            deepcopy(conflict["result"]["data"]["conflicts"]) if conflict else []
        )
        report["summary"] = (
            "打包执行成功，但材料包仍有缺项或未决事项；文件名候选不代表材料审核通过"
            if plan["missing"] or plan["unresolved"]
            else "打包执行和文件字节验证成功；文件名候选不代表材料审核通过"
        )
        return report

    def report(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            entry = self._entry(task_id)
            if entry["task"]["status"] != "completed" or entry["report"] is None:
                raise TaskConflict("Report is not available")
            return deepcopy(entry["report"])
