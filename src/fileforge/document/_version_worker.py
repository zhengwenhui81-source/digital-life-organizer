"""Single-call stdin/stdout worker; no file reads, services or descendants."""

import json
import sys

from fileforge.document._version_core import compare


def main() -> None:
    payload = json.loads(sys.stdin.buffer.read())
    result = compare(payload["documents"])
    sys.stdout.buffer.write(
        json.dumps(
            result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


if __name__ == "__main__":
    main()
