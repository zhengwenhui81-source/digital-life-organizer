"""Start the production Agent on an OS-assigned loopback port, with secure local key entry."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--configure',action='store_true',help='Masked local key dialog; never saves the key')
    parser.add_argument('--reload',action='store_true',help='Development reload of this independent service only; active in-memory tasks are lost on reload')
    args=parser.parse_args()
    if args.manifest.exists():parser.error('Manifest must be a new file')
    if args.configure:
        import tkinter as tk
        from tkinter import simpledialog
        root=tk.Tk();root.withdraw()
        key=simpledialog.askstring('Digital Life Organizer 安全配置',
            '为独立新版Agent输入DeepSeek API Key。仅保存在该进程内存，不写入文件。取消则不启动。',show='*',parent=root)
        root.destroy()
        if not key:raise SystemExit('Cancelled; no service or model request started')
        os.environ['FILEFORGE_AGENT_PLANNER_API_KEY']=key
        os.environ['FILEFORGE_AGENT_PLANNER_BASE_URL']='https://api.deepseek.com/v1'
        os.environ['FILEFORGE_AGENT_PLANNER_MODEL']='deepseek-chat'
    if not os.getenv('FILEFORGE_AGENT_PLANNER_API_KEY'):
        raise SystemExit('No API Key in this process. Use --configure for masked local entry; never paste a key into chat.')
    os.environ['FILEFORGE_AGENT_PLANNER_MODE']='llm'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    import uvicorn
    listener=socket.socket()
    if os.name=='nt':listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    listener.bind(('127.0.0.1',0));listener.listen(socket.SOMAXCONN)
    port=listener.getsockname()[1]
    info={'url':f'http://127.0.0.1:{port}/','mode':'llm',
          'model':os.getenv('FILEFORGE_AGENT_PLANNER_MODEL'),
          'base_url':os.getenv('FILEFORGE_AGENT_PLANNER_BASE_URL'),
          'code_root':str(Path(__file__).resolve().parents[1]),'process_id':os.getpid()}
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    with args.manifest.open('x',encoding='utf-8') as stream:json.dump(info,stream,ensure_ascii=False,indent=2)
    print(info['url'],flush=True)
    config=uvicorn.Config('fileforge.api.server:app',host='127.0.0.1',port=port,log_level='warning',reload=args.reload,
                          reload_dirs=[str(Path(__file__).resolve().parents[1]/'src/fileforge/agent'),str(Path(__file__).resolve().parents[1]/'src/fileforge/api')] if args.reload else None)
    server=uvicorn.Server(config)
    try:
        if args.reload:
            from uvicorn.supervisors import ChangeReload
            ChangeReload(config,target=server.run,sockets=[listener]).run()
        else:server.run(sockets=[listener])
    finally:listener.close()


if __name__=='__main__':main()
