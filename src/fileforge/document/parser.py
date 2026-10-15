"""TXT-only document parsing with path-based document identity."""

from __future__ import annotations

import hashlib
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fileforge.extractor import text


def read_document(path: str) -> dict[str, Any]:
    """Return a TXT Document in the shared ToolResult envelope.

    Identity uses the resolved absolute target path, not file contents.
    Only TXT is supported. Task workspace authorization belongs to the caller.
    """
    return _read_txt(path)


def _read_txt(path: str) -> dict[str, Any]:
    """Read a complete TXT file using FileForge's existing decoding behavior.

    No 2000-character snippet limit is applied: sys.maxsize is the maximum
    representable Python string length. The existing extractor reads all bytes,
    detects encoding with chardet and uses replacement decoding for bad bytes.
    Empty/whitespace-only content is an explicit failure, as in the extractor.
    The caller must enforce the task workspace boundary before invoking this
    low-level reader. This function never writes the source file.
    """
    try:
        source = Path(path).expanduser().resolve(strict=True)
        identity_path = os.path.normcase(str(source)).encode("utf-8")
        file_id = "file_" + hashlib.sha256(identity_path).hexdigest()
        info = source.stat()
        if not stat.S_ISREG(info.st_mode):
            return _failure("Path is not a regular file")
        if source.suffix.lower() != ".txt":
            return _failure("Unsupported document format; only TXT is supported")
        content = text.extract(source, max_chars=sys.maxsize)
        if content is None:
            return _failure("Document is empty or contains only whitespace")
        document = {
            "file_id": file_id,
            "path": str(source),
            "filename": source.name,
            "extension": ".txt",
            "text": content,
            "size": info.st_size,
            "modified_time": datetime.fromtimestamp(info.st_mtime, tz=UTC).isoformat(),
            "metadata": {},
        }
    except FileNotFoundError:
        return _failure("File not found")
    except PermissionError:
        return _failure("Permission denied reading document")
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        return _failure(f"Document read failed: {exc}")
    return {
        "success": True,
        "tool": "read_document",
        "data": {"document": document},
        "message": "TXT document read successfully",
        "error": None,
    }


def _failure(error: str) -> dict[str, Any]:
    """Build the existing contract's failure envelope."""
    return {
        "success": False,
        "tool": "read_document",
        "data": None,
        "message": "Document read failed",
        "error": error,
    }
