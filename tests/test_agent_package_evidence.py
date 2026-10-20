"""Package preflight must reject stale or incomplete analysis evidence."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import pytest

from fileforge.agent.package_evidence import (
    bind_selected_snapshots,
    revalidate_documents,
)
from fileforge.document import read_document


def _read(path: Path) -> dict:
    result = read_document(path=str(path))
    assert result["success"], result
    return result


def test_revalidation_binds_complete_document_and_current_raw_bytes(tmp_path: Path):
    source = tmp_path / "notice.txt"
    source.write_text("报名要求甲", encoding="utf-8")
    original = _read(source)

    checked = revalidate_documents(str(tmp_path), [(7, original)])

    assert checked[7]["file_id"] == original["data"]["document"]["file_id"]
    assert checked[7]["path"] == str(source)
    assert checked[7]["size"] == source.stat().st_size
    assert len(checked[7]["sha256"]) == 64


def test_same_path_size_and_restored_mtime_cannot_reuse_stale_analysis(tmp_path: Path):
    source = tmp_path / "notice.txt"
    source.write_text("规则甲", encoding="utf-8")
    original = _read(source)
    old = source.stat()
    source.write_text("规则乙", encoding="utf-8")
    os.utime(source, ns=(old.st_atime_ns, old.st_mtime_ns))
    assert source.stat().st_size == old.st_size
    assert source.stat().st_mtime_ns == old.st_mtime_ns

    with pytest.raises(ValueError, match="Document changed"):
        revalidate_documents(str(tmp_path), [(0, original)])


def test_metadata_extra_field_and_type_are_compared_strictly(tmp_path: Path):
    source = tmp_path / "notice.txt"
    source.write_text("通知正文", encoding="utf-8")
    original = _read(source)
    stale = deepcopy(original)
    stale["data"]["document"]["extra"] = {"number": 1.0}
    with pytest.raises(ValueError, match="Document changed"):
        revalidate_documents(str(tmp_path), [(0, stale)])

    contradictory = deepcopy(original)
    contradictory["data"]["document"]["metadata"]["number"] = 1.0
    first = deepcopy(contradictory)
    first["data"]["document"]["metadata"]["number"] = 1
    with pytest.raises(ValueError, match="Contradictory"):
        revalidate_documents(str(tmp_path), [(0, first), (1, contradictory)])


def test_reread_failure_and_change_during_read_block_preview(tmp_path: Path):
    source = tmp_path / "notice.txt"
    source.write_text("原始通知", encoding="utf-8")
    original = _read(source)

    with pytest.raises(ValueError, match="reread failed"):
        revalidate_documents(
            str(tmp_path),
            [(0, original)],
            reader=lambda **_: {
                "success": False,
                "tool": "read_document",
                "data": None,
            },
        )

    def changing_reader(**kwargs):
        result = read_document(**kwargs)
        source.write_text("新通知书", encoding="utf-8")
        return result

    with pytest.raises(ValueError, match="source bytes changed"):
        revalidate_documents(str(tmp_path), [(0, original)], reader=changing_reader)


def test_unread_evidence_and_symlink_are_rejected(tmp_path: Path):
    source = tmp_path / "notice.txt"
    source.write_text("通知正文", encoding="utf-8")
    original = _read(source)
    failed = {**original, "success": False, "data": None}
    with pytest.raises(ValueError, match="successful read_document"):
        revalidate_documents(str(tmp_path), [(0, failed)])

    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        return  # Windows may disallow creating a test symlink.
    linked = deepcopy(original)
    linked["data"]["document"]["path"] = str(link)
    with pytest.raises(ValueError, match="link"):
        revalidate_documents(str(tmp_path), [(0, linked)])


def test_d_plan_snapshot_must_match_a_checked_bytes(tmp_path: Path):
    source = tmp_path / "material.txt"
    source.write_text("选定材料", encoding="utf-8")
    original = _read(source)
    checked = revalidate_documents(str(tmp_path), [(3, original)])
    evidence = checked[3]
    plan = {
        "selected_files": [
            {
                "source": {
                    key: evidence[key] for key in ("file_id", "path", "filename")
                },
                "snapshot": {
                    key: evidence[key] for key in ("size", "mtime_ns", "sha256")
                },
            }
        ]
    }
    assert bind_selected_snapshots(plan, checked) == {0: 3}

    changed = deepcopy(plan)
    changed["selected_files"][0]["snapshot"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="differs"):
        bind_selected_snapshots(changed, checked)

    changed = deepcopy(plan)
    changed["selected_files"][0]["source"]["file_id"] = "file_other"
    with pytest.raises(ValueError, match="no checked Document"):
        bind_selected_snapshots(changed, checked)
