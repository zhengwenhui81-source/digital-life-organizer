"""Characterize A's existing primitives in disposable fixtures, not production glue.

Direct low-level calls here are test-only, with authorized temporary-file writes.
They do NOT prove TaskService approval, organization execution or a public seam.
The production organization module imports none of these helpers.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from fileforge.agent import package_execution as execution
from fileforge.agent.package_fs import anchored_mkdir, guarded_entries


def fixture(tmp_path: Path):
    folder = tmp_path / "中文 空格"
    folder.mkdir()
    source = folder / "来源.bin"
    source.write_bytes(b"fixture source bytes\x00\xff")
    target_dir = tmp_path / "fixture-output"
    target_dir.mkdir()
    info = source.stat()
    return (
        source,
        target_dir / source.name,
        hashlib.sha256(source.read_bytes()).hexdigest(),
        (info.st_dev, info.st_ino),
    )


def test_candidate_directory_primitive_is_exclusive(tmp_path):
    folder = tmp_path / "独占目录"
    anchored_mkdir(folder, tmp_path)
    sentinel = folder / "keep"
    sentinel.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        anchored_mkdir(folder, tmp_path)
    assert guarded_entries(folder, tmp_path) == {"keep"}
    assert sentinel.read_bytes() == b"keep"


def test_candidate_copy_checks_bytes_and_preserves_original(tmp_path):
    source, target, digest, identity = fixture(tmp_path)
    before = source.read_bytes(), source.stat().st_mtime_ns
    result, cleanup = execution._copy_one(source, target, digest, tmp_path, identity)
    assert result["success"], result
    assert target.read_bytes() == before[0]
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    assert cleanup == {
        "status": "not_attempted",
        "reason": "copy_succeeded",
        "residual_state": "absent",
    }


def test_candidate_copy_never_overwrites_existing_target(tmp_path):
    source, target, digest, identity = fixture(tmp_path)
    target.write_bytes(b"existing sentinel")
    result, cleanup = execution._copy_one(source, target, digest, tmp_path, identity)
    assert result["success"] is False and result["data"] is None
    assert target.read_bytes() == b"existing sentinel"
    assert cleanup["status"] == "not_attempted"


def test_candidate_copy_rejects_same_stat_different_bytes(tmp_path):
    source, target, digest, identity = fixture(tmp_path)
    info = source.stat()
    source.write_bytes(b"x" * info.st_size)
    os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns))
    result, cleanup = execution._copy_one(source, target, digest, tmp_path, identity)
    assert result["success"] is False and result["data"] is None
    assert "digest" in result["error"]
    assert not target.exists() and cleanup["residual_state"] == "absent"


def test_candidate_copy_keeps_failure_and_owned_fragment(tmp_path, monkeypatch):
    source, target, digest, identity = fixture(tmp_path)
    real_write = execution.os.write

    def fail_after_partial_write(fd, data):
        real_write(fd, data[:3])
        raise OSError("fixture write failure")

    monkeypatch.setattr(execution.os, "write", fail_after_partial_write)
    result, cleanup = execution._copy_one(source, target, digest, tmp_path, identity)
    assert result["success"] is False and result["data"] is None
    assert "fixture write failure" in result["error"]
    assert target.read_bytes() == source.read_bytes()[:3]
    assert cleanup["status"] == "not_attempted"
    assert cleanup["residual_state"] == "owned_fragment"


def test_candidate_copy_rejects_link_source_without_copy(tmp_path):
    source, target, digest, identity = fixture(tmp_path)
    link = source.parent / "链接.bin"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Real symlink creation unavailable: {exc}")
    result, _ = execution._copy_one(link, target, digest, tmp_path, identity)
    assert result["success"] is False and result["data"] is None
    assert not target.exists()
