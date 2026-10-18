"""Development-only HTTP/browser harness; real tools, fixed planner, no LLM.

Only fixture creation/cleanup writes files, inside a fresh TemporaryDirectory.
The Agent itself can call only the five read-only tools below.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService
from fileforge.api.agent import get_service, router

READ_ONLY = frozenset({"list_files", "read_document", "compare_versions", "extract_requirements", "match_requirements"})
LABELS = {
    "mixed": "单候选 / 多候选 / 本次未找到候选",
    "no_candidates": "有要求，无候选",
    "no_requirements": "未提取到要求",
    "read_failure": "真实空 TXT 读取失败",
    "empty": "无文件可读",
}


def prepare_workspaces(root: Path) -> dict[str, Path]:
    """Synthetic input files only; no fabricated Document/ToolResult payloads."""
    workspaces = {}
    for name in LABELS:
        workspace = root / name
        notice, materials = workspace / "notice", workspace / "materials"
        notice.mkdir(parents=True)
        materials.mkdir()
        workspaces[name] = workspace
        if name == "empty":
            continue
        # These strings are fixture contents, never classifier/planner decisions.
        text = "必须提交阶段说明\n必须提交进度记录\n必须提交验证摘要\n"
        if name == "no_requirements":
            text = "这是合成的阅读说明，没有明确提交要求。\n"
        (notice / "说明.txt").write_text(text, encoding="utf-8")
        if name == "mixed":
            for filename, content in [("阶段说明.txt", "阶段说明示例"), ("进度记录_v1.txt", "第一阶段记录"), ("进度记录_v2.txt", "第二阶段记录")]:
                (materials / filename).write_text("合成项目的阶段进度记录与说明。\n" * 30 + content, encoding="utf-8")
        elif name == "no_requirements":
            (materials / "随记.txt").write_text("合成的阅读随记", encoding="utf-8")
        elif name == "read_failure":
            (materials / "空白.txt").write_text("", encoding="utf-8")
    return workspaces


def fixed_planner(task_id: str, goal: str, workspace: str) -> dict:
    """Fixed fixture layout, not natural-language planning or material selection."""
    root = Path(workspace)
    steps = [
        {"tool": "list_files", "description": "离线固定步骤：列出说明目录", "arguments": {"workspace": str(root / "notice"), "recursive": False}},
        {"tool": "read_document", "description": "离线固定步骤：读取说明", "arguments": {}},
        {"tool": "extract_requirements", "description": "离线固定步骤：真实提取材料要求", "arguments": {}},
        {"tool": "list_files", "description": "离线固定步骤：列出候选目录", "arguments": {"workspace": str(root / "materials"), "recursive": False}},
        {"tool": "read_document", "description": "离线固定步骤：读取真实候选；空集合交由现有 Agent 处理", "arguments": {}},
        {"tool": "match_requirements", "description": "离线固定步骤：真实文件名候选匹配（非内容审核）", "arguments": {}},
        {"tool": "compare_versions", "description": "离线固定步骤：真实版本分析（不选择最终文件）", "arguments": {}},
    ]
    return validate_plan({"steps": steps}, task_id, goal)


class ReadOnlyRouter:
    """Development guard around the existing router, not a tool implementation."""

    def __init__(self, delay: float = 0):
        self.router = ToolRouter()
        self.delay = delay

    def call(self, name, arguments, *, approved=False):
        if name not in READ_ONLY or approved:
            return {"success": False, "tool": name, "data": None, "message": "Offline harness is read-only", "error": "Offline harness rejects this tool or approval"}
        if self.delay:
            time.sleep(self.delay)  # Display pacing only; no altered results.
        return self.router.call(name, arguments, approved=False)


def create_app(workspaces: dict[str, Path], delay: float = 0) -> FastAPI:
    """Reuse original Agent HTTP routes with an app-local service override."""
    app = FastAPI(title="Offline fixed-planner integration — NOT LLM", docs_url=None, redoc_url=None, openapi_url=None)
    service = TaskService(planner=fixed_planner, router=ReadOnlyRouter(delay))
    allowed = {path.resolve() for path in workspaces.values()}

    async def offline_service(request: Request):
        if request.method == "POST" and request.url.path == "/api/agent/tasks":
            try:
                data = await request.json()
                path = data.get("workspace") if isinstance(data, dict) else None
                if not isinstance(path, str) or Path(path).expanduser().resolve() not in allowed:
                    raise ValueError("Only this run's temporary fixture Workspaces are allowed")
            except (ValueError, OSError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return service

    app.include_router(router)
    app.dependency_overrides[get_service] = offline_service
    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def page():
        html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        # This response alone uses system fonts; production HTML stays untouched.
        html = "\n".join(line for line in html.splitlines() if not ("<link" in line and ("fonts.googleapis.com" in line or "fonts.gstatic.com" in line)))
        config = json.dumps([{"name": name, "label": LABELS[name], "workspace": str(path.resolve())} for name, path in workspaces.items()], ensure_ascii=False).replace("<", "\\u003c")
        injection = '<script id="offlineContext" type="application/json">' + config + '</script><script src="/static/offline-browser.js"></script>'
        return HTMLResponse(html.replace("</body>", injection + "</body>"), headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"})

    @app.get("/api/sessions")
    def sessions():
        return {"sessions": []}  # This isolated service has no FileForge sessions.

    @app.get("/favicon.ico", status_code=204)
    def favicon():
        return Response(status_code=204)

    return app


def bind_listener(port: int = 0) -> socket.socket:
    """Reserve and retain the actual listening socket; never probe then rebind."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(socket.SOMAXCONN)
        listener.setblocking(False)
        return listener
    except BaseException:
        listener.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="0 lets the OS select a free loopback port (default)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--step-delay", type=float, default=0.35, help="Read-only tool pacing, 0..2 seconds")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535 or not 0 <= args.step_delay <= 2:
        parser.error("port must be 0..65535; step-delay must be 0..2")
    import uvicorn

    try:
        listener = bind_listener(args.port)
    except OSError as exc:
        parser.exit(1, f"Cannot bind 127.0.0.1:{args.port}: {exc}. Use the default --port 0; no other service was changed.\n")
    with listener, tempfile.TemporaryDirectory(prefix="dlo_offline_browser_") as directory:
        app = create_app(prepare_workspaces(Path(directory)), args.step_delay)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info"))
        url = f"http://127.0.0.1:{port}"
        print(f"OFFLINE FIXED PLANNER - NOT LLM - READ ONLY\nBound socket: {url}\nTemporary fixtures: {directory}\nCtrl+C to stop and remove temporary fixtures.", flush=True)
        stop_opening = threading.Event()
        browser_thread = None
        if not args.no_browser:
            def open_when_ready():
                while not stop_opening.wait(0.1):
                    if server.should_exit:
                        return
                    if server.started:
                        print(f"Ready: {url}", flush=True)
                        webbrowser.open(url)
                        return
            browser_thread = threading.Thread(target=open_when_ready, daemon=True)
            browser_thread.start()
        try:
            # Pass the reserved socket itself, not merely its selected port.
            server.run(sockets=[listener])
        except KeyboardInterrupt:
            # Uvicorn gracefully handles SIGINT then re-raises it on current
            # versions. Still unwind TemporaryDirectory and the socket normally.
            pass
        finally:
            stop_opening.set()
            if browser_thread is not None:
                browser_thread.join(timeout=1)


if __name__ == "__main__":
    main()
