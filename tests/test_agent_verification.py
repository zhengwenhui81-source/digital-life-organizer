"""Verification rechecks package and archive contents without writing files."""

from __future__ import annotations

from pathlib import Path

from fileforge.tools import verify_result


def test_verify_expected_files_and_missing_item(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "form.txt").write_text("form")
    result = verify_result(
        "task_001",
        {"files": ["package/form.txt", "package/missing.txt"], "archive": []},
        str(tmp_path),
    )
    assert result["success"] is True
    assert result["data"]["passed"] is False
    assert [check["passed"] for check in result["data"]["checks"]] == [True, False]


def test_verify_archive_result(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "old.txt").write_text("old")
    result = verify_result(
        "task_001", {"files": [], "archive": ["archive/old.txt"]}, str(tmp_path)
    )
    assert result["data"]["passed"] is True


def test_verify_rejects_workspace_escape(tmp_path: Path) -> None:
    result = verify_result("task_001", {"files": ["../outside.txt"]}, str(tmp_path))
    assert result["success"] is False
    assert "escapes workspace" in result["error"]
