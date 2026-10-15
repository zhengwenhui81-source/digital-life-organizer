"""Agent file tools follow the shared envelope and reject unsafe writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from fileforge.tools import (
    copy_file,
    create_folder,
    find_duplicates,
    list_files,
    move_file,
    search_files,
)


def test_read_tools_reuse_scan_and_dedup(tmp_path: Path) -> None:
    (tmp_path / ".forgeignore").write_text("*.tmp\n")
    (tmp_path / "form_v1.txt").write_text("same")
    (tmp_path / "form_v2.txt").write_text("same")
    (tmp_path / "hidden.tmp").write_text("same")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "notes.md").write_text("notes")

    listed = list_files(str(tmp_path), recursive=False)
    assert listed["success"] is True
    assert {item["filename"] for item in listed["data"]["files"]} == {
        ".forgeignore", "form_v1.txt", "form_v2.txt"
    }
    matches = search_files(str(tmp_path), "FORM", ["txt"])
    assert {item["filename"] for item in matches["data"]["matches"]} == {
        "form_v1.txt", "form_v2.txt"
    }
    groups = find_duplicates(str(tmp_path))
    assert groups["success"] is True
    assert len(groups["data"]["duplicate_groups"]) == 1
    assert {item["filename"] for item in groups["data"]["duplicate_groups"][0]} == {
        "form_v1.txt", "form_v2.txt"
    }


def test_mutations_require_approval(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_text("original")
    dest = tmp_path / "dest.txt"
    folder = tmp_path / "new"
    for result in (
        create_folder(str(folder)),
        copy_file(str(src), str(dest)),
        move_file(str(src), str(dest)),
    ):
        assert result["success"] is False
        assert result["data"] is None
        assert "approval" in result["error"].lower()
    assert src.read_text() == "original"
    assert not dest.exists()
    assert not folder.exists()


def test_approved_copy_and_move_never_overwrite(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_text("source")
    existing = tmp_path / "existing.txt"
    existing.write_text("keep")
    assert copy_file(str(src), str(existing), approved=True)["success"] is False
    assert move_file(str(src), str(existing), approved=True)["success"] is False
    assert existing.read_text() == "keep"
    assert src.read_text() == "source"

    folder = tmp_path / "package"
    assert create_folder(str(folder), approved=True)["success"] is True
    copied = folder / "copied.txt"
    assert copy_file(str(src), str(copied), approved=True)["success"] is True
    assert src.exists() and copied.read_text() == "source"
    moved = folder / "archived.txt"
    assert move_file(str(src), str(moved), approved=True)["success"] is True
    assert not src.exists() and moved.read_text() == "source"


def test_failed_read_returns_tool_result(tmp_path: Path) -> None:
    result = list_files(str(tmp_path / "missing"))
    assert result == {
        "success": False,
        "tool": "list_files",
        "data": None,
        "message": "list_files failed",
        "error": f"Workspace is not a directory: {tmp_path / 'missing'}",
    }


def test_failed_copy_removes_only_new_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "source.txt"
    src.write_text("content")
    dest = tmp_path / "partial.txt"

    def fail_copy(input_file: object, output_file: object) -> None:
        output_file.write(b"partial")
        raise OSError("copy failed")

    monkeypatch.setattr("fileforge.tools.files.shutil.copyfileobj", fail_copy)
    result = copy_file(str(src), str(dest), approved=True)
    assert result["success"] is False
    assert src.read_text() == "content"
    assert not dest.exists()

