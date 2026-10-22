"""Start this checkout with the main project's venv and local Planner secrets."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

CODE_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-root', type=Path, default=CODE_ROOT.with_name('digital-life-organizer'))
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--check', action='store_true', help='Offline config/import check, never a model request')
    parser.add_argument('--model', default='deepseek-flash', help='Official DeepSeek model; explicit override for this launcher')
    parser.add_argument('--planner-timeout',type=float,default=90,help='Planner request timeout in seconds, 1..300; retries remain disabled')
    args = parser.parse_args()
    config = args.config_root.resolve()
    if Path(sys.prefix).resolve() != (config / '.venv').resolve():
        parser.exit(2, 'Use the main project .venv/Scripts/python.exe interpreter.\n')
    try:
        # Reuse the existing literal .env loader; never evaluate configuration.
        spec = importlib.util.spec_from_file_location('local_settings', config / 'demo/start_course22.py')
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        settings = loader.load_settings(config / '.env')
        if not args.model.strip() or not 1 <= args.port <= 65535 or not 1 <= args.planner_timeout <= 300:
            raise ValueError('Invalid model/port')
        settings['FILEFORGE_AGENT_PLANNER_TIMEOUT_SECONDS'] = str(args.planner_timeout)
        settings['FILEFORGE_AGENT_PLANNER_MODE'] = 'llm'
        settings['FILEFORGE_AGENT_PLANNER_MODEL'] = args.model
        # This launcher is explicitly for the official DeepSeek service.
        settings['FILEFORGE_AGENT_PLANNER_BASE_URL'] = 'https://api.deepseek.com'
    except Exception:
        parser.exit(2, 'Cannot load local settings. Check main project .env and existing Demo settings loader. No secret values printed.\n')
    os.environ.update(settings)
    sys.path.insert(0, str(CODE_ROOT / 'src'))
    from fileforge.agent import planner
    from fileforge.api import server
    if Path(planner.__file__).resolve() != CODE_ROOT / 'src/fileforge/agent/planner.py':
        parser.exit(2, 'Unexpected imported source; refusing startup.\n')
    if server.FRONTEND_DIR.resolve() != CODE_ROOT / 'frontend':
        parser.exit(2, 'Unexpected frontend source; refusing startup.\n')
    head = subprocess.check_output(['git', '-C', str(CODE_ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    print(json.dumps({'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(),
        'python': sys.executable, 'python_version': sys.version.split()[0], 'venv':sys.prefix,
        'code_root': str(CODE_ROOT), 'head': head, 'planner_file': planner.__file__,
        'planner_sha256': hashlib.sha256(Path(planner.__file__).read_bytes()).hexdigest(),
        'frontend':str(server.FRONTEND_DIR), 'env_source': str(config / '.env'),
        'api_key_loaded': bool(os.environ.get('FILEFORGE_AGENT_PLANNER_API_KEY')),
        'mode':'llm', 'model':args.model, 'planner_timeout_seconds':planner._planner_timeout(), 'max_retries':0, 'base_url':settings['FILEFORGE_AGENT_PLANNER_BASE_URL'],
        'model_connection':'not tested by startup/health', 'model_requests':0}, ensure_ascii=False), flush=True)
    if args.check:
        return
    listener = socket.socket()
    if os.name == 'nt':
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(('127.0.0.1', args.port))
    except OSError:
        listener.close()
        parser.exit(2, 'Port occupied; no process stopped. Inspect the existing listener first.\n')
    listener.listen(socket.SOMAXCONN)
    import uvicorn
    print(f'Open http://127.0.0.1:{args.port}/ (keep terminal open; Ctrl+C stops this service)', flush=True)
    try:
        uvicorn.Server(uvicorn.Config(server.app, host='127.0.0.1', port=args.port)).run(sockets=[listener])
    finally:
        listener.close()


if __name__ == '__main__':
    main()
