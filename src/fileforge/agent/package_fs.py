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
    """Load native handle-relative Windows file operations."""
    import ctypes
    from ctypes import wintypes

    class UnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(UnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    class IoStatusBlock(ctypes.Structure):
        _fields_ = [
            ("Status", ctypes.c_size_t),
            ("Information", ctypes.c_size_t),
        ]

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    class ByHandleInfo(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("creation", FileTime),
            ("access", FileTime),
            ("write", FileTime),
            ("volume", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    native = ctypes.WinDLL("ntdll", use_last_error=True)
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
    kernel.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleInfo),
    )
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    native.NtCreateFile.argtypes = (
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.ULONG,
        ctypes.POINTER(ObjectAttributes),
        ctypes.POINTER(IoStatusBlock),
        wintypes.LPVOID,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.LPVOID,
        wintypes.ULONG,
    )
    native.NtCreateFile.restype = wintypes.LONG
    native.RtlNtStatusToDosError.argtypes = (wintypes.LONG,)
    native.RtlNtStatusToDosError.restype = wintypes.ULONG
    return (
        ctypes,
        wintypes,
        kernel,
        native,
        UnicodeString,
        ObjectAttributes,
        IoStatusBlock,
        ByHandleInfo,
    )


def _win_check(handle: int, *, directory: bool) -> None:
    ctypes, _, kernel, _, _, _, _, Info = _windows_api()
    info = Info()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if info.attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
        raise ValueError("Package path contains a link or reparse point")
    if bool(info.attributes & 0x10) != directory:  # FILE_ATTRIBUTE_DIRECTORY
        raise ValueError("Package opened object has unexpected file type")


def _win_root(path: Path) -> int:
    ctypes, _, kernel, _, _, _, _, _ = _windows_api()
    handle = kernel.CreateFileW(
        str(path),
        0x001000A0,  # SYNCHRONIZE | FILE_READ_ATTRIBUTES | FILE_TRAVERSE
        0x1 | 0x2,  # no FILE_SHARE_DELETE
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        _win_check(handle, directory=True)
        return handle
    except BaseException:
        kernel.CloseHandle(handle)
        raise


def _win_relative(
    parent: int,
    name: str,
    *,
    directory: bool,
    create: bool,
    write_parent: bool = False,
) -> int:
    """NtCreateFile relative to an already-open parent, not its mutable name."""
    (
        ctypes,
        wintypes,
        kernel,
        native,
        Unicode,
        Object,
        IoStatus,
        _,
    ) = _windows_api()
    if not name or name in {".", ".."} or "\\" in name or "/" in name:
        raise ValueError("Package child name is invalid")
    buffer = ctypes.create_unicode_buffer(name)
    name_struct = Unicode(
        len(name) * ctypes.sizeof(ctypes.c_wchar),
        (len(name) + 1) * ctypes.sizeof(ctypes.c_wchar),
        ctypes.cast(buffer, wintypes.LPWSTR),
    )
    obj = Object(
        ctypes.sizeof(Object),
        parent,
        ctypes.pointer(name_struct),
        0x40,  # OBJ_CASE_INSENSITIVE; opened child reparse is checked by handle
        None,
        None,
    )
    io = IoStatus()
    out = wintypes.HANDLE()
    access = (
        0x001000A0 | (0x2 | 0x4 if write_parent else 0)
        if directory
        else (0x00100000 | (0x40000000 if create else 0x80000000))
    )
    options = (
        (0x1 if directory else 0x40)  # DIRECTORY_FILE / NON_DIRECTORY_FILE
        | 0x20  # FILE_SYNCHRONOUS_IO_NONALERT
        | 0x00200000  # FILE_OPEN_REPARSE_POINT
    )
    status = native.NtCreateFile(
        ctypes.byref(out),
        access,
        ctypes.byref(obj),
        ctypes.byref(io),
        None,
        0x10 if directory and create else 0x80,
        0x1 | 0x2,  # share READ|WRITE; no DELETE
        2 if create else 1,  # FILE_CREATE / FILE_OPEN
        options,
        None,
        0,
    )
    if status < 0:
        code = native.RtlNtStatusToDosError(status)
        if code in (80, 183):
            raise FileExistsError(f"Package target already exists: {name}")
        if code in (2, 3):
            raise FileNotFoundError(f"Package path not found: {name}")
        if code in (5, 32):
            raise PermissionError(f"Package object not accessible: {name}")
        raise OSError(
            f"NtCreateFile failed on {name}: {code} "
            f"(NTSTATUS {status & 0xFFFFFFFF:#x})"
        )
    handle = out.value
    try:
        _win_check(handle, directory=directory)
        return handle
    except BaseException:
        kernel.CloseHandle(handle)
        raise


@contextmanager
def _parent(path: Path, root: Path, *, writing: bool = False) -> Iterator[int]:
    """Pin all directory components through path.parent until the operation."""
    _scoped(path, root)
    if os.name == "nt":
        _, _, kernel, _, _, _, _, _ = _windows_api()
        held = []
        try:
            current = Path(path.anchor)
            if not current.anchor or current.anchor.startswith("\\\\"):
                raise ValueError("UNC Package path is unsupported")
            handle = _win_root(current)
            held.append(handle)
            parts = path.parent.parts[1:]
            for index, part in enumerate(parts):
                handle = _win_relative(
                    held[-1],
                    part,
                    directory=True,
                    create=False,
                    write_parent=(index == len(parts) - 1 and writing),
                )
                held.append(handle)
            yield held[-1]
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
    with _parent(path, root, writing=bool(flags & os.O_CREAT)) as parent:
        if os.name == "nt":
            import msvcrt

            _, _, kernel, _, _, _, _, _ = _windows_api()
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR))
            exclusive = bool(flags & os.O_CREAT and flags & os.O_EXCL)
            if flags & os.O_CREAT and not exclusive:
                raise ValueError("Package creates require O_EXCL")
            handle = _win_relative(parent, path.name, directory=False, create=exclusive)
            try:
                descriptor_flags = getattr(os, "O_BINARY", 0) | (
                    os.O_WRONLY if writing else os.O_RDONLY
                )
                fd = msvcrt.open_osfhandle(handle, descriptor_flags)
                handle = None  # CRT owns the handle
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
    with _parent(path, root, writing=True) as parent:
        if os.name == "nt":
            _, _, kernel, _, _, _, _, _ = _windows_api()
            handle = _win_relative(parent, path.name, directory=True, create=True)
            kernel.CloseHandle(handle)
        else:
            os.mkdir(path.name, dir_fd=parent)


def guarded_entries(path: Path, root: Path) -> set[str]:
    """Read entries without following a late directory reparse replacement."""
    with _parent(path / "__package_entry_check__", root) as parent:
        if os.name == "nt":
            return {entry.name for entry in path.iterdir()}
        with os.scandir(parent) as entries:
            return {entry.name for entry in entries}
