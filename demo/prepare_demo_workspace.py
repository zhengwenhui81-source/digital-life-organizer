"""Restore demo mtimes using only the standard library; never change contents."""

from __future__ import annotations

import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEMO_TIMES = {
    "比赛通知.pdf": "2026-10-10T09:00:00+08:00",
    "补充通知.pdf": "2026-10-14T09:00:00+08:00",
    "报名表.docx": "2026-10-13T09:30:00+08:00",
    "项目介绍_v1.docx": "2026-10-11T10:00:00+08:00",
    "项目介绍_最终版.docx": "2026-10-14T16:30:00+08:00",
    "学生证.jpg": "2026-10-09T09:00:00+08:00",
    "身份证.pdf": "2026-10-09T09:00:00+08:00",
    "个人简历.docx": "2026-10-09T11:00:00+08:00",
    "会议记录.txt": "2026-10-08T14:00:00+08:00",
}


def main() -> int:
    root = Path(__file__).resolve().parent / "sample_workspace"
    try:
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"Expected a real demo directory: {root}")
        # Preflight every input before touching timestamps. Extra files are ignored.
        updates = []
        for name, value in DEMO_TIMES.items():
            path = root / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or path.resolve().parent != root.resolve():
                raise ValueError(f"Expected a regular demo file, not a link: {path}")
            stamp_ns = int(datetime.fromisoformat(value).timestamp()) * 1_000_000_000
            updates.append((path, info.st_atime_ns, stamp_ns))
        for path, atime_ns, stamp_ns in updates:
            # Windows Python builds may not support follow_symlinks=False.
            # Targets have already been checked as ordinary files above.
            os.utime(path, ns=(atime_ns, stamp_ns))
            if path.stat().st_mtime_ns != stamp_ns:
                raise OSError(f"Filesystem did not preserve the expected mtime: {path}")
            value = datetime.fromtimestamp(
                stamp_ns // 1_000_000_000, tz=timezone(timedelta(hours=8))
            ).isoformat()
            print(f"{path.name}: {value}")
        print(f"Prepared {len(updates)} demo mtimes. No file contents changed.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Demo preparation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
