"""Workspace-anchored, exclusive Package file operations.

POSIX opens each ancestor relative to its held directory descriptor. Windows
holds every ancestor directory without FILE_SHARE_DELETE and opens final files
with FILE_FLAG_OPEN_REPARSE_POINT; a concurrent rename/reparse replacement
cannot redirect a path while its ancestor locks are held. A concurrent move
after a handle is released remains an observable filesystem race (v1 limit).
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _scoped(path: Path, root: Path) -> None:
    if (
        not path.is_absolute()
        or not root.is_absolute()
        or ".." in path.parts
        or not path.is_relative_to(root)
    ):
        raise ValueError("Package path escapes workspace")


def _windows_api():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    return ctypes, kernel


def _win_open(kernel, ctypes, path: Path, access: int, creation: int, attrs: int):
    # Do not grant FILE_SHARE_DELETE: hold the object at the checked name.
    handle = kernel.CreateFileW(
        str(path), access, 0x1 | 0x2, None, creation, attrs, None
    )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _win_check(path: Path, *, directory: bool) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Package path contains a link or reparse point")
    if directory and not stat.S_ISDIR(info.st_mode):
        raise ValueError("Package parent is not a directory")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise ValueError("Package target is not a regular file")


@contextmanager
def _parent(path: Path, root: Path) -> Iterator[int | None]:
    """Pin all directory components through path.parent until the operation."""
    _scoped(path, root)
    if os.name == "nt":
        ctypes, kernel = _windows_api()
        held = []
        try:
            current = Path(path.anchor)
            if not current.anchor or current.anchor.startswith("\\\\"):
                raise ValueError("UNC Package path is unsupported")
            for part in (None, *path.parent.parts[1:]):
                if part is not None:
                    current = current / part
                handle = _win_open(
                    kernel,
                    ctypes,
                    current,
                    0x80,  # FILE_READ_ATTRIBUTES
                    3,  # OPEN_EXISTING
                    0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
                )
                held.append(handle)
                _win_check(current, directory=True)
            yield None
        finally:
            for handle in reversed(held):
                kernel.CloseHandle(handle)
        return

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_DIRECTORY", 0) or not getattr(os, "O_NOFOLLOW", 0):
        raise OSError("Platform cannot anchor Package directories")
    fd = os.open(path.anchor, flags)
    try:
        for component in path.parent.parts[1:]:
            child = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def anchored_open(path: Path, root: Path, flags: int, mode: int = 0o600) -> int:
    """Return a regular-file descriptor opened within a pinned parent chain."""
    with _parent(path, root) as parent:
        if os.name == "nt":
            import msvcrt

            ctypes, kernel = _windows_api()
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR))
            exclusive = bool(flags & os.O_CREAT and flags & os.O_EXCL)
            if flags & os.O_CREAT and not exclusive:
                raise ValueError("Package creates require O_EXCL")
            handle = _win_open(
                kernel,
                ctypes,
                path,
                0x40000000 if writing else 0x80000000,  # GENERIC_WRITE / READ
                1 if exclusive else 3,  # CREATE_NEW / OPEN_EXISTING
                0x00200000 | 0x80,  # OPEN_REPARSE_POINT | NORMAL
            )
            try:
                _win_check(path, directory=False)
                descriptor_flags = getattr(os, "O_BINARY", 0) | (
                    os.O_WRONLY if writing else os.O_RDONLY
                )
                fd = msvcrt.open_osfhandle(handle, descriptor_flags)
                handle = None  # CRT owns the handle after successful conversion
            finally:
                if handle is not None:
                    kernel.CloseHandle(handle)
        else:
            fd = os.open(path.name, flags | os.O_NOFOLLOW, mode, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("Package file is not regular")
            return fd
        except BaseException:
            os.close(fd)
            raise


def anchored_mkdir(path: Path, root: Path) -> None:
    with _parent(path, root) as parent:
        if os.name == "nt":
            os.mkdir(path)
        else:
            os.mkdir(path.name, dir_fd=parent)


def guarded_entries(path: Path, root: Path) -> set[str]:
    """Read entries without following a late directory reparse replacement."""
    with _parent(path / "__package_entry_check__", root) as parent:
        if os.name == "nt":
            return {entry.name for entry in path.iterdir()}
        with os.scandir(parent) as entries:
            return {entry.name for entry in entries}
