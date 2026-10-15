"""TXT document contract tests using disposable source files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from fileforge.document import read_document


@pytest.mark.parametrize(
    ("content", "encoding"),
    [
        ("报名材料\n" * 1000 + "全文结尾", "utf-8"),
        ("Résumé professionnel\n" * 20, "latin-1"),
        ("中文报名材料\n" * 20, "utf-16"),
    ],
)
def test_full_text_contract_and_source_unchanged(
    tmp_dir: Path, content: str, encoding: str
) -> None:
    source = tmp_dir / "HARNESS_document.TXT"
    raw = content.encode(encoding)
    source.write_bytes(raw)
    before = source.stat()
    result = read_document(str(source))
    assert set(result) == {"success", "tool", "data", "message", "error"}
    assert result["success"] is True
    assert result["tool"] == "read_document"
    assert result["error"] is None
    document = result["data"]["document"]
    assert set(document) == {
        "file_id",
        "path",
        "filename",
        "extension",
        "text",
        "size",
        "modified_time",
        "metadata",
    }
    assert (
        document["file_id"]
        == "file_"
        + hashlib.sha256(
            os.path.normcase(str(source.resolve())).encode("utf-8")
        ).hexdigest()
    )
    assert document["path"] == str(source.resolve())
    assert document["filename"] == source.name
    assert document["extension"] == ".txt"
    assert document["text"] == content
    assert document["size"] == len(raw)
    assert datetime.fromisoformat(document["modified_time"]) == datetime.fromtimestamp(
        before.st_mtime, tz=UTC
    )
    assert isinstance(document["metadata"], dict)
    json.dumps(result)
    assert source.read_bytes() == raw
    assert source.stat().st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize("content", ["", " \n\t "])
def test_empty_content_is_explicit_failure(tmp_dir: Path, content: str) -> None:
    source = tmp_dir / "HARNESS_empty.txt"
    source.write_text(content)
    result = read_document(str(source))
    assert result["success"] is False
    assert result["data"] is None
    assert "empty" in result["error"].lower()
    assert source.read_text() == content


@pytest.mark.parametrize("extension", [".pdf", ".docx", ".xlsx", ".md", ".bin"])
def test_only_txt_is_supported(tmp_dir: Path, extension: str) -> None:
    source = tmp_dir / ("HARNESS_other" + extension)
    source.write_bytes(b"sample")
    result = read_document(str(source))
    assert result["success"] is False
    assert result["data"] is None
    assert "unsupported" in result["error"].lower()
    assert source.read_bytes() == b"sample"


def test_missing_file(tmp_dir: Path) -> None:
    result = read_document(str(tmp_dir / "HARNESS_missing.txt"))
    assert result["success"] is False
    assert result["data"] is None
    assert "not found" in result["error"].lower()


def test_directory_is_not_a_document(tmp_dir: Path) -> None:
    source = tmp_dir / "HARNESS_directory.txt"
    source.mkdir()
    result = read_document(str(source))
    assert result["success"] is False
    assert "regular file" in result["error"].lower()


@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("I/O failure")])
def test_read_failure(tmp_dir: Path, error: OSError) -> None:
    source = tmp_dir / "HARNESS_unreadable.txt"
    source.write_text("source remains intact")
    with patch("fileforge.document.parser.text.extract", side_effect=error):
        result = read_document(str(source))
    assert result["success"] is False
    assert result["data"] is None
    assert result["error"]
    assert source.read_text() == "source remains intact"


def test_expanduser_uses_existing_text_reader(tmp_dir: Path) -> None:
    source = tmp_dir / "HARNESS_home.txt"
    source.write_text("expanded path content", encoding="utf-8")
    before = source.stat().st_mtime_ns
    with patch("os.path.expanduser", return_value=str(tmp_dir)):
        result = read_document("~/HARNESS_home.txt")
    assert result["success"] is True
    assert result["data"]["document"]["file_id"] == (
        read_document(str(source))["data"]["document"]["file_id"]
    )
    assert result["data"]["document"]["path"] == str(source.resolve())
    assert result["data"]["document"]["text"] == "expanded path content"
    assert source.read_text(encoding="utf-8") == "expanded path content"
    assert source.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    "error", [OSError("cannot resolve"), RuntimeError("link loop")]
)
def test_path_resolution_failure(error: Exception) -> None:
    with patch.object(Path, "resolve", side_effect=error):
        result = read_document("HARNESS_unresolved.txt")
    assert result["success"] is False
    assert result["data"] is None
    assert "read failed" in result["error"].lower()


def test_identity_survives_repeat_reads_and_content_changes(tmp_dir: Path) -> None:
    source = tmp_dir / "HARNESS_identity.txt"
    source.write_text("original", encoding="utf-8")
    first = read_document(str(source))["data"]["document"]
    repeated = read_document(str(source))["data"]["document"]
    assert first["file_id"] == repeated["file_id"]
    source.write_text("updated text", encoding="utf-8")
    updated = read_document(str(source))["data"]["document"]
    assert first["file_id"] == updated["file_id"]
    assert updated["text"] == "updated text"


def test_copy_and_rename_change_identity(tmp_dir: Path) -> None:
    source = tmp_dir / "HARNESS_source.txt"
    source.write_text("same content", encoding="utf-8")
    original = read_document(str(source))["data"]["document"]
    copied = tmp_dir / "HARNESS_copy.txt"
    shutil.copyfile(source, copied)
    copy_doc = read_document(str(copied))["data"]["document"]
    assert copy_doc["text"] == original["text"]
    assert copy_doc["file_id"] != original["file_id"]
    renamed = tmp_dir / "HARNESS_renamed.txt"
    source.rename(renamed)
    renamed_doc = read_document(str(renamed))["data"]["document"]
    assert renamed_doc["file_id"] != original["file_id"]
    destination = tmp_dir / "HARNESS_subdirectory"
    destination.mkdir()
    moved = destination / renamed.name
    renamed.rename(moved)
    moved_doc = read_document(str(moved))["data"]["document"]
    assert moved_doc["file_id"] != renamed_doc["file_id"]
    assert moved_doc["text"] == original["text"]


def test_relative_absolute_and_symlink_paths_agree(
    tmp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_dir / "HARNESS_target.txt"
    source.write_text("target content", encoding="utf-8")
    monkeypatch.chdir(tmp_dir)
    absolute = read_document(str(source))["data"]["document"]
    relative = read_document("./HARNESS_target.txt")["data"]["document"]
    assert absolute == relative
    link = tmp_dir / "HARNESS_alias.txt"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are not available in this environment")
    assert read_document(str(link))["data"]["document"] == absolute


@pytest.mark.skipif(os.name == "nt", reason="Linux case-sensitive path semantics")
def test_linux_does_not_lowercase_paths(tmp_dir: Path) -> None:
    upper = tmp_dir / "HARNESS_CASE.txt"
    lower = tmp_dir / "HARNESS_case.txt"
    upper.write_text("same", encoding="utf-8")
    lower.write_text("same", encoding="utf-8")
    assert read_document(str(upper))["data"]["document"]["file_id"] != (
        read_document(str(lower))["data"]["document"]["file_id"]
    )


def test_utf8_path_encoding_failure_returns_envelope() -> None:
    with patch.object(Path, "resolve", return_value=Path("/HARNESS_\udcff.txt")):
        result = read_document("HARNESS_bad_path.txt")
    assert result["success"] is False
    assert result["data"] is None
    assert result["tool"] == "read_document"
    assert result["error"]


def test_broken_symlink_returns_failure(tmp_dir: Path) -> None:
    link = tmp_dir / "HARNESS_broken.txt"
    try:
        link.symlink_to(tmp_dir / "HARNESS_missing.txt")
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are not available in this environment")
    result = read_document(str(link))
    assert result["success"] is False
    assert result["data"] is None
    assert "not found" in result["error"].lower()
