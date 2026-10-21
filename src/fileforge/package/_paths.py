"""Native local paths and stable, streaming read-only source observations."""

import hashlib
import os
import re
import stat
import unicodedata
from pathlib import Path, PureWindowsPath

_WINDOWS = os.name == "nt"


def collision_key(name):
    return unicodedata.normalize("NFC", name).casefold()


def check_name(name):
    if (
        not name
        or not name.strip()
        or name.endswith((".", " "))
        or any(unicodedata.category(c) == "Cc" or c in '<>:"/\\|?*' for c in name)
        or name.strip(".") == ""
        or re.fullmatch(
            r"(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])", name.split(".")[0], re.I
        )
    ):
        raise ValueError(f"Unsafe cross-platform target name: {name!r}")


def native_path(raw):
    if type(raw) is not str or not raw or "\x00" in raw:
        raise ValueError("Path must be a nonempty native absolute string")
    win = PureWindowsPath(raw)
    if (
        raw.startswith(("//", "\\\\"))
        or "://" in raw
        or (os.name != "nt" and (win.drive or "\\" in raw))
        or (os.name == "nt" and (not win.drive or raw.startswith("\\\\")))
    ):
        raise ValueError(f"Unsupported foreign/UNC/device/URI path: {raw!r}")
    p = Path(raw)
    if not p.is_absolute() or ".." in p.parts or "." in re.split(r"[/\\]", raw):
        raise ValueError(f"Absolute non-traversing native path required: {raw!r}")
    return p


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def check_chain(path):
    """Inspect ancestors without resolving links; missing suffix is permitted."""
    for part in list(reversed(path.parents)) + [path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if _is_link(info):
            raise ValueError(f"Links/reparse points are forbidden: {part}")
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Non-directory ancestor: {part}")


def scope(path, workspace):
    if not path.is_relative_to(workspace):
        raise ValueError(f"Path outside workspace: {path}")
    check_chain(path)


def prepare_paths(workspace, destination):
    root = native_path(workspace)
    dest = native_path(destination)
    check_chain(root)
    if not root.is_dir():
        raise ValueError("workspace must be an existing directory")
    scope(dest, root)
    check_name(dest.name)
    if dest == root or os.path.lexists(dest):
        raise ValueError("Package destination is already occupied")
    if not dest.parent.is_dir():
        raise ValueError("Destination parent must already exist")
    return root, dest


def _signature(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _same_signature(left, right, *, compare_ctime=True):
    left_signature = _signature(left)
    right_signature = _signature(right)
    if not compare_ctime:
        left_signature = left_signature[:-1]
        right_signature = right_signature[:-1]
    return left_signature == right_signature


def _same_cross_api_signature(left, right):
    # Windows can report slightly different ctime_ns values for the same file
    # through lstat() and fstat(). Each API's before/after ctime is still checked.
    return _same_signature(left, right, compare_ctime=not _WINDOWS)


def snapshot(path, workspace):
    scope(path, workspace)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"Source is not a regular file: {path}")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if not _same_cross_api_signature(opened, before) or not stat.S_ISREG(
            opened.st_mode
        ):
            raise ValueError("Source changed before reading")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
        scope(path, workspace)
        observed = path.lstat()
        if (
            size != before.st_size
            or not _same_signature(opened, after)
            or not _same_signature(before, observed)
            or not _same_cross_api_signature(after, observed)
        ):
            raise ValueError(f"Source changed while reading: {path}")
        return dict(size=size, mtime_ns=after.st_mtime_ns, sha256=digest.hexdigest())
    finally:
        os.close(fd)
