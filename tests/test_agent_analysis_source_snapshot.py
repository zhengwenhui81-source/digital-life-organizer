"""Agent analysis arguments retain the full earlier read snapshot."""

from copy import deepcopy
from pathlib import Path

import pytest

from fileforge.agent.service import TaskService


def test_analysis_rejects_document_with_different_numeric_type(tmp_path: Path) -> None:
    path = str(tmp_path / "notice.txt")
    original = {"file_id": "notice-id", "path": path, "metadata": {"revision": 1}}
    supplied = deepcopy(original)
    supplied["metadata"]["revision"] = 1.0
    step = {
        "step_id": "step_002",
        "tool": "extract_requirements",
        "arguments": {"documents": [supplied]},
    }
    results = [
        {
            "success": True,
            "tool": "read_document",
            "data": {"document": original},
        }
    ]
    resolver = TaskService()._scoped_resolver(tmp_path, [step])
    with pytest.raises(ValueError, match="successful read_document"):
        resolver(step, results)

    step["arguments"]["documents"] = [deepcopy(original)]
    assert resolver(step, results) == {"documents": [original]}


def test_analysis_rejects_document_with_extra_field(tmp_path: Path) -> None:
    path = str(tmp_path / "notice.txt")
    original = {"file_id": "notice-id", "path": path, "metadata": {}}
    supplied = {**original, "extra": None}
    step = {
        "step_id": "step_002",
        "tool": "detect_conflicts",
        "arguments": {"documents": [supplied]},
    }
    results = [
        {
            "success": True,
            "tool": "read_document",
            "data": {"document": original},
        }
    ]
    with pytest.raises(ValueError, match="successful read_document"):
        TaskService()._scoped_resolver(tmp_path, [step])(step, results)

