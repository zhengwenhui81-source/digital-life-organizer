"""Windows stat-channel compatibility must preserve change detection."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from fileforge.package import _paths
from tests import test_package_planning as fixtures

request_data = fixtures.request_data


def _with_ctime(info, ctime_ns):
    return SimpleNamespace(
        st_dev=info.st_dev,
        st_ino=info.st_ino,
        st_mode=info.st_mode,
        st_size=info.st_size,
        st_mtime_ns=info.st_mtime_ns,
        st_ctime_ns=ctime_ns,
        st_file_attributes=getattr(info, "st_file_attributes", 0),
    )


def _with_inode(info, inode):
    return SimpleNamespace(
        st_dev=info.st_dev,
        st_ino=inode,
        st_mode=info.st_mode,
        st_size=info.st_size,
        st_mtime_ns=info.st_mtime_ns,
        st_ctime_ns=info.st_ctime_ns,
        st_file_attributes=getattr(info, "st_file_attributes", 0),
    )


def test_windows_allows_cross_api_ctime_skew_but_keeps_identity_hash(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.txt"
    source.write_bytes(b"stable source bytes")
    original_lstat = Path.lstat

    def skewed_lstat(path):
        info = original_lstat(path)
        if path == source:
            return _with_ctime(info, info.st_ctime_ns + 1_007_400)
        return info

    monkeypatch.setattr(Path, "lstat", skewed_lstat)
    monkeypatch.setattr(_paths, "_WINDOWS", True)

    result = _paths.snapshot(source, tmp_path)

    assert result["size"] == len(b"stable source bytes")
    assert result["sha256"] == hashlib.sha256(b"stable source bytes").hexdigest()


def test_non_windows_still_requires_cross_api_ctime_match(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_bytes(b"stable source bytes")
    original_lstat = Path.lstat

    def skewed_lstat(path):
        info = original_lstat(path)
        if path == source:
            return _with_ctime(info, info.st_ctime_ns + 1_007_400)
        return info

    monkeypatch.setattr(Path, "lstat", skewed_lstat)
    monkeypatch.setattr(_paths, "_WINDOWS", False)

    with pytest.raises(ValueError, match="changed before reading"):
        _paths.snapshot(source, tmp_path)


def test_windows_still_rejects_ctime_change_within_fstat_channel(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_bytes(b"stable source bytes")
    original_fstat = _paths.os.fstat
    calls = 0

    def changing_fstat(fd):
        nonlocal calls
        calls += 1
        info = original_fstat(fd)
        if calls == 1:
            return info
        return _with_ctime(info, info.st_ctime_ns + 1)

    monkeypatch.setattr(_paths.os, "fstat", changing_fstat)
    monkeypatch.setattr(_paths, "_WINDOWS", True)

    with pytest.raises(ValueError, match="changed while reading"):
        _paths.snapshot(source, tmp_path)


def test_windows_still_rejects_ctime_change_within_lstat_channel(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_bytes(b"stable source bytes")
    original_lstat = Path.lstat
    calls = 0

    def changing_lstat(path):
        nonlocal calls
        info = original_lstat(path)
        if path == source:
            calls += 1
            if calls == 4:
                return _with_ctime(info, info.st_ctime_ns + 1)
        return info

    monkeypatch.setattr(Path, "lstat", changing_lstat)
    monkeypatch.setattr(_paths, "_WINDOWS", True)

    with pytest.raises(ValueError, match="changed while reading"):
        _paths.snapshot(source, tmp_path)


def test_windows_rejects_path_identity_change_during_read(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_bytes(b"stable source bytes")
    original_lstat = Path.lstat
    original_read = _paths.os.read
    path_replaced = False

    def replacing_read(fd, size):
        nonlocal path_replaced
        data = original_read(fd, size)
        path_replaced = True
        return data

    def replaced_path_lstat(path):
        info = original_lstat(path)
        if path == source and path_replaced:
            return _with_inode(info, info.st_ino + 1)
        return info

    monkeypatch.setattr(_paths.os, "read", replacing_read)
    monkeypatch.setattr(Path, "lstat", replaced_path_lstat)
    monkeypatch.setattr(_paths, "_WINDOWS", True)

    with pytest.raises(ValueError, match="changed while reading"):
        _paths.snapshot(source, tmp_path)


def test_windows_filesystem_replacement_during_read_when_supported(
    request_data, tmp_path, monkeypatch
):
    source = Path(request_data["selected_files"][0]["source"]["path"])
    replacement = tmp_path / "replacement"
    replacement.write_bytes(source.read_bytes())
    original_read = _paths.os.read
    replaced = False
    monkeypatch.setattr(_paths, "_WINDOWS", True)

    def replacing_read(fd, size):
        nonlocal replaced
        data = original_read(fd, size)
        if not replaced:
            replaced = True
            try:
                replacement.replace(source)
            except PermissionError as exc:
                if _paths.os.name == "nt" and getattr(exc, "winerror", None) == 5:
                    pytest.skip(
                        "Windows denied replacing a file while it is open; "
                        "the deterministic path identity test covers detection"
                    )
                raise
        return data

    monkeypatch.setattr(_paths.os, "read", replacing_read)
    with pytest.raises(ValueError, match="changed while reading"):
        _paths.snapshot(source, Path(request_data["task"]["workspace"]))
