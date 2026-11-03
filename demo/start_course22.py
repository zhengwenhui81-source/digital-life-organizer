"""Start the existing course Demo with local, non-exported Planner credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
import webbrowser

PROJECT = Path(__file__).resolve().parents[1]
PREFIX = "FILEFORGE_AGENT_PLANNER_"
NAMES = {PREFIX + name for name in ("MODE", "MODEL", "BASE_URL", "API_KEY")}


def load_settings(path: Path) -> dict[str, str]:
    """Read literal single-line .env settings; never evaluate shell expressions.

    Only the four Planner settings are consumed. Quoted literals and comments
    are supported; interpolation and multiline values fail closed.
    """
    values = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if name not in NAMES:
            continue
        if not separator or name in values:
            raise ValueError(f"Invalid or duplicate Planner setting at line {number}")
        value = value.strip()
        if value.startswith(('"', "'")):
            match = re.fullmatch(r"(['\"])(.*?)\1\s*(?:#.*)?", value)
            if not match:
                raise ValueError(f"Use a single-line literal at line {number}")
            value = match.group(2)
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if "${" in value or "\x00" in value:
            raise ValueError(f"Unsupported Planner value at line {number}")
        values[name] = value
    # Explicit file values win over stale shell values. Do not persist to OS env.
    defaults = {
        PREFIX + "MODE": "llm",
        PREFIX + "MODEL": "deepseek-chat",
        PREFIX + "BASE_URL": "https://api.deepseek.com/v1",
    }
    settings = defaults | values
    if not settings.get(PREFIX + "API_KEY", "").strip():
        raise ValueError("Set FILEFORGE_AGENT_PLANNER_API_KEY in project root .env")
    if settings[PREFIX + "MODE"] != "llm":
        raise ValueError("This real Demo launcher requires Planner mode llm")
    if not settings[PREFIX + "MODEL"].strip():
        raise ValueError("Planner model is empty")
    url = urlsplit(settings[PREFIX + "BASE_URL"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use an HTTPS Planner base URL without credentials/query/fragment")
    return settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=PROJECT,
                        help="Backend checkout (use the original validated checkout for recording)")
    parser.add_argument("--port", type=int, default=51851)
    parser.add_argument("--check", action="store_true", help="Offline config/import check; no services or model calls")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--backend", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        settings = load_settings(PROJECT / ".env")
        code_root = args.code_root.resolve(strict=True)
        planner_path = code_root / "src/fileforge/agent/planner.py"
        if not planner_path.is_file() or not 1 <= args.port <= 65535:
            raise ValueError("Invalid backend checkout or port")
    except (OSError, ValueError):
        # Do not print exceptions: filesystem/parser errors may contain secrets.
        parser.exit(2, "Local configuration invalid. Check .env literal settings, API key presence, code-root and port.\n")

    if args.check:
        os.environ.update(settings)
        sys.path.insert(0, str(code_root / "src"))
        import fileforge.agent.planner as planner

        print(json.dumps({"config_source": str(PROJECT / ".env"),
                          "api_key_loaded": bool(os.environ.get(PREFIX + "API_KEY")),
                          "mode": settings[PREFIX + "MODE"],
                          "model": settings[PREFIX + "MODEL"],
                          "base_url": settings[PREFIX + "BASE_URL"],
                          "planner_file": planner.__file__,
                          "model_requests": 0}, ensure_ascii=False))
        return
    if args.backend:
        os.environ.update(settings)
        sys.path.insert(0, str(code_root / "src"))
        import uvicorn

        uvicorn.run("fileforge.api.server:app", host="127.0.0.1", port=args.port)
        return

    # Never take over an existing listener or stop an unrelated process.
    with socket.socket() as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            parser.exit(2, "Backend port occupied; existing services left untouched.\n")
    children = []
    backend_url = f"http://127.0.0.1:{args.port}"
    opener = build_opener(ProxyHandler({}))
    try:
        # Keys travel through process memory, never arguments, manifests or logs.
        backend = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
                                    "--backend", "--code-root", str(code_root),
                                    "--port", str(args.port)], cwd=PROJECT)
        children.append(backend)
        for _ in range(120):
            if backend.poll() is not None:
                raise RuntimeError("Backend stopped during startup")
            try:
                with opener.open(backend_url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("Backend health check timed out")
        # course22_demo requires a new root; never use a material Workspace.
        root = Path(tempfile.mkdtemp(prefix="dlo-course22-start-")) / "session"
        frontend = subprocess.Popen([sys.executable, "-B", str(PROJECT / "demo/course22_demo.py"),
                                     "--root", str(root), "--code-root", str(code_root),
                                     "--backend-url", backend_url], cwd=PROJECT)
        children.append(frontend)
        for _ in range(120):
            if frontend.poll() is not None:
                raise RuntimeError("Demo page stopped during startup")
            manifest = root / "server.json"
            try:
                url = json.loads(manifest.read_text(encoding="utf-8"))["url"]
                with opener.open(url, timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, ValueError, KeyError):
                time.sleep(0.25)
        else:
            raise RuntimeError("Demo page health check timed out")
        print(f"Demo: {url}\nBackend: {backend_url}\nKeep this terminal open; Ctrl+C stops only these two services.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)


if __name__ == "__main__":
    main()
