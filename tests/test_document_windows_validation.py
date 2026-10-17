"""Supplemental parser checks; Windows results require a real Windows run."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fileforge.document import read_document
from tests.test_document_parser import _make_docx, _make_pdf, _make_xlsx


def _sample(tmp_path: Path, extension: str) -> Path:
    """Create real files only inside pytest's temporary directory."""
    folder = tmp_path / "HARNESS_中文 空格目录"
    folder.mkdir()
    source = folder / ("HARNESS_中文 材料" + extension)
    content = "long content " * 400
    if extension == ".pdf":
        _make_pdf(source, [[content[:3000]], [content[3000:], "END_MARKER"]])
    elif extension == ".docx":
        _make_docx(source, [content, "中文正文", "END_MARKER"])
    elif extension == ".xlsx":
        _make_xlsx(source, {"首个表": [[content]], "末尾表": [["END_MARKER"]]})
    else:
        source.write_text(content + "中文正文\nEND_MARKER", encoding="utf-8")
    return source.rename(source.with_suffix(extension.upper()))


@pytest.mark.parametrize("extension", [".txt", ".pdf", ".docx", ".xlsx"])
def test_unicode_space_uppercase_repeat_and_immediate_rename(
    tmp_path: Path, extension: str
) -> None:
    source = _sample(tmp_path, extension)
    before = (source.read_bytes(), source.stat().st_mtime_ns)
    first = read_document(str(source))
    assert first["success"] is True, first
    document = first["data"]["document"]
    assert document["extension"] == extension
    assert len(document["text"]) > 2000
    assert document["text"].endswith("END_MARKER")
    if extension == ".xlsx":
        assert "[首个表]" in document["text"] and "[末尾表]" in document["text"]
    for _ in range(3):
        assert read_document(str(source)) == first
        assert before == (source.read_bytes(), source.stat().st_mtime_ns)
        # No retry/sleep/GC workaround: immediate renaming must work.
        moved = source.rename(source.with_name("HARNESS_改名 " + source.name))
        result = read_document(str(moved))
        assert result["success"] is True, result
        assert result["data"]["document"]["file_id"] != document["file_id"]
        moved.rename(source)
        assert read_document(str(source)) == first
        assert before == (source.read_bytes(), source.stat().st_mtime_ns)


@pytest.mark.parametrize("extension", [".pdf", ".docx", ".xlsx"])
def test_corrupt_file_standard_failure_and_handle_release(
    tmp_path: Path, extension: str
) -> None:
    source = tmp_path / ("HARNESS_损坏 文件" + extension.upper())
    source.write_bytes(b"not a valid document")
    before = (source.read_bytes(), source.stat().st_mtime_ns)
    for _ in range(3):
        result = read_document(str(source))
        assert set(result) == {"success", "tool", "data", "message", "error"}
        assert result["success"] is False
        assert result["tool"] == "read_document"
        assert result["data"] is None
        assert result["message"] and result["error"]
        moved = source.rename(source.with_name("HARNESS_改名 " + source.name))
        moved.rename(source)
        assert before == (source.read_bytes(), source.stat().st_mtime_ns)


@pytest.mark.skipif(os.name != "nt", reason="Requires real Windows path semantics")
@pytest.mark.parametrize("extension", [".txt", ".pdf", ".docx", ".xlsx"])
def test_windows_case_alias_keeps_identity(tmp_path: Path, extension: str) -> None:
    source = _sample(tmp_path, extension)
    alias = source.with_name(source.name.swapcase())
    if not alias.exists():
        pytest.skip("Test directory is case-sensitive; case alias not available")
    first = read_document(str(source))
    second = read_document(str(alias))
    assert first["success"] is True and second["success"] is True
    assert first["data"]["document"]["file_id"] == (
        second["data"]["document"]["file_id"]
    )
