"""Read-only preflight boundaries, race observations and no-mutation guarantees."""

import copy
import os
from pathlib import Path

import pytest

from fileforge.package import _paths, plan_package
from tests import test_package_planning as fixtures

request_data = fixtures.request_data


def failed(request):
    result = plan_package(**request)
    assert result["success"] is False and result["data"] is None, result
    assert result["error"]
    return result


@pytest.mark.parametrize(
    "name",
    [
        "PACKAGE_REPORT.md",
        "package_report.MD",
        "CON.txt",
        "NUL",
        "a?.txt",
        "a.txt.",
        "a.txt ",
        "..",
        "a\n.txt",
    ],
)
def test_reserved_and_unsafe_names(request_data, name):
    ref = request_data["selected_files"][0]["source"]
    ref["filename"] = name
    ref["path"] = str(Path(request_data["task"]["workspace"]) / name)
    # Avoid a different same-ID reference masking target safety validation.
    request_data["analysis"] = dict.fromkeys(request_data["analysis"])
    failed(request_data)


@pytest.mark.parametrize("name", ["课程笔记.TXT", "课程笔记.txt"])
def test_distinct_ids_target_collision(request_data, name, tmp_path):
    folder = tmp_path / "another"
    folder.mkdir()
    path = folder / name
    path.write_text("body")
    other = copy.deepcopy(request_data["selected_files"][0])
    other["source"] = dict(file_id="other", path=str(path), filename=name)
    request_data["selected_files"].append(other)
    failed(request_data)


def test_unicode_collision(request_data, tmp_path):
    request_data["analysis"] = dict.fromkeys(request_data["analysis"])
    selected = []
    for i, name in enumerate(["é.txt", "e\u0301.txt"]):
        p = tmp_path / name
        p.write_text("e")
        selected.append(
            dict(
                source=dict(file_id=str(i), path=str(p), filename=name),
                requirements=[],
                reason="proposal",
            )
        )
    request_data["selected_files"] = selected
    failed(request_data)


@pytest.mark.parametrize("kind", ["file", "directory", "dangling_link", "link"])
def test_occupied_destination(request_data, kind, tmp_path):
    p = Path(request_data["destination"])
    if kind == "file":
        p.write_text("preexisting")
    elif kind == "directory":
        p.mkdir()
    else:
        try:
            p.symlink_to(
                tmp_path / ("missing" if kind == "dangling_link" else "通知.txt")
            )
        except (OSError, NotImplementedError):
            pytest.skip("symlink unavailable on this platform")
    failed(request_data)
    assert os.path.lexists(p)


@pytest.mark.parametrize("which", ["source", "workspace", "destination_parent"])
def test_link_boundaries(request_data, tmp_path, which):
    link = tmp_path / "alias"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable on this platform")
    if which == "source":
        request_data["analysis"] = dict.fromkeys(request_data["analysis"])
        request_data["selected_files"][0]["source"]["path"] = str(link / "课程笔记.txt")
    elif which == "workspace":
        request_data["task"]["workspace"] = str(link)
    else:
        request_data["destination"] = str(link / "package")
    failed(request_data)


@pytest.mark.parametrize(
    "path",
    [
        "relative/package",
        "C:\\data\\package",
        "//server/share/package",
        "file:///tmp/package",
        "/tmp/a/../package",
    ],
)
def test_unsupported_paths(request_data, path):
    # POSIX-specific foreign Windows check is conditional.
    if os.name == "nt" and path.startswith("C:"):
        pytest.skip("native Windows path")
    request_data["destination"] = path
    failed(request_data)


def test_outside_source_and_destination(request_data, tmp_path):
    request_data["destination"] = str(tmp_path.parent / "outside-package")
    failed(request_data)
    request_data["destination"] = str(tmp_path / "package")
    request_data["task"]["workspace"] = str(tmp_path / "inner")
    (tmp_path / "inner").mkdir()
    failed(request_data)


@pytest.mark.parametrize("kind", ["missing", "directory", "dangling"])
def test_invalid_source(request_data, kind, tmp_path):
    request_data["analysis"] = dict.fromkeys(request_data["analysis"])
    p = tmp_path / "invalid.txt"
    if kind == "directory":
        p.mkdir()
    if kind == "dangling":
        try:
            p.symlink_to(tmp_path / "missing")
        except (OSError, NotImplementedError):
            pytest.skip("symlink unavailable")
    request_data["selected_files"][0]["source"].update(path=str(p), filename=p.name)
    failed(request_data)


def test_unreadable_source(request_data, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("controlled unreadable source")

    monkeypatch.setattr(_paths.os, "open", denied)
    assert "unreadable" in failed(request_data)["error"]


def test_observable_change_during_stream(request_data, monkeypatch):
    p = Path(request_data["selected_files"][0]["source"]["path"])
    read = os.read
    changed = False

    def changing(fd, size):
        nonlocal changed
        data = read(fd, size)
        if not changed:
            changed = True
            with p.open("ab") as stream:
                stream.write(b"changed")
        return data

    monkeypatch.setattr(_paths.os, "read", changing)
    assert "changed" in failed(request_data)["error"].lower()


def test_no_mutating_operations(request_data, monkeypatch, tmp_path):
    def inventory():
        return {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    before = inventory()
    original = copy.deepcopy(request_data)

    def forbidden(*args, **kwargs):
        raise AssertionError("filesystem mutation attempted")

    for method in (
        "mkdir",
        "write_text",
        "write_bytes",
        "unlink",
        "rename",
        "replace",
        "touch",
    ):
        monkeypatch.setattr(Path, method, forbidden)
    import shutil

    monkeypatch.setattr(shutil, "copyfile", forbidden)
    real_open = os.open

    def readonly(path, flags, *args, **kwargs):
        assert not flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        )
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", readonly)
    assert plan_package(**request_data)["success"]
    request_data["selected_files"] = []
    failed(request_data)
    request_data["selected_files"] = original["selected_files"]
    assert inventory() == before and request_data == original


def test_same_path_different_id_not_identity_error(request_data):
    item = copy.deepcopy(request_data["selected_files"][0])
    item["source"]["file_id"] = "different-id"
    # Each identity is retained; rejection is a target collision, not ID/path identity.
    request_data["selected_files"].append(item)
    assert "collision" in failed(request_data)["error"].lower()


def test_replacement_during_read_is_rejected(request_data, tmp_path, monkeypatch):
    source = Path(request_data["selected_files"][0]["source"]["path"])
    replacement = tmp_path / "replacement"
    replacement.write_bytes(source.read_bytes())
    original = os.read
    changed = False

    def replacing(fd, size):
        nonlocal changed
        data = original(fd, size)
        if not changed:
            changed = True
            replacement.replace(source)
        return data

    monkeypatch.setattr(os, "read", replacing)
    failed(request_data)


def test_destination_parent_must_exist(request_data, tmp_path):
    request_data["destination"] = str(tmp_path / "missing-parent" / "package")
    assert "parent" in failed(request_data)["error"].lower()


def test_filename_path_mismatch(request_data):
    request_data["analysis"] = dict.fromkeys(request_data["analysis"])
    request_data["selected_files"][0]["source"]["filename"] = "different.txt"
    assert "filename" in failed(request_data)["error"].lower()
