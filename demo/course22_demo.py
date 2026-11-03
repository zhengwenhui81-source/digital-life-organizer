"""Course material preparation + UI evidence for an EXISTING real Agent HTTP service.

Every take creates a new copy; never reset/delete an existing workspace.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import socket
import sys
import threading
import uuid

REPORTS = [f"课程设计报告_v{i}.docx" for i in (1, 2, 3)]
NOTICE = "课程设计_提交要求.docx"
OUTPUT = "课程设计_智能整理结果"
CATEGORIES = ("01_最终提交材料", "02_源代码", "03_实验数据与图表", "04_配置与运行说明", "05_历史版本与参考", "06_无关文件")
ROUTES = {
    "课程设计报告_v3.docx": CATEGORIES[0],
    "课程设计报告_v1.docx": CATEGORIES[4],
    "课程设计报告_v2.docx": CATEGORIES[4],
    "main.cpp": CATEGORIES[1],
    "controller.cpp": CATEGORIES[1],
    "controller.h": CATEGORIES[1],
    "config.json": CATEGORIES[3],
    "trajectory_error.csv": CATEGORIES[2],
    "trajectory_comparison.png": CATEGORIES[2],
    "error_curve.png": CATEGORIES[2],
    "实验结果说明.docx": CATEGORIES[2],
    "测试记录.docx": CATEGORIES[2],
    "程序运行说明.docx": CATEGORIES[3],
    NOTICE: CATEGORIES[3],
    "plot_results.py": CATEGORIES[1],
    "backup_main_old.cpp": CATEGORIES[4],
    "legacy_controller_v0.cpp": CATEGORIES[4],
    "项目简介.txt": CATEGORIES[0],
    "项目验收备忘.pdf": CATEGORIES[4],
    "notes_todo.md": CATEGORIES[4],
    "会议记录_2026-10-12.md": CATEGORIES[4],
    "个人购物清单.txt": CATEGORIES[5],
}
GOAL = "请根据课程设计要求，整理当前工作空间中的全部22份材料。识别最终提交材料、源代码、实验数据、配置说明、历史版本和无关文件。请保留所有原始文件，先生成整理方案，得到我的确认后再创建分类文件夹并复制材料。"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    result = {}
    for p in Path(root).iterdir():
        info = p.lstat()
        if p.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Demo refuses links/reparse points")
        if p.is_file():
            result[p.name] = dict(sha256=digest(p), size=info.st_size, mtime_ns=str(info.st_mtime_ns))
    return result


def target(root, name, routes=None):
    return Path(root) / OUTPUT / (routes or ROUTES)[name] / name


def read_rules(text):
    """Parse source-to-category mappings from the task requirements."""
    routes = {}
    for line in text.splitlines():
        if not line.startswith('[整理规则] '):
            continue
        pair = line[len('[整理规则] '):].split(' => ')
        if len(pair) != 2:
            raise ValueError('课程整理规则格式不完整')
        name, raw = pair
        p = PurePosixPath(raw.replace('\\', '/'))
        invalid = (
            name in routes
            or not name
            or '/' in name
            or '\\' in name
            or len(p.parts) != 3
            or p.parts[0] != OUTPUT
            or p.parts[1] not in CATEGORIES
            or p.parts[2] != name
        )
        if invalid:
            raise ValueError('课程整理规则重复、越界或包含未知目标')
        routes[name] = p.parts[1]
    if set(routes) != set(ROUTES):
        raise ValueError('课程整理规则必须覆盖全部22份材料且不得包含额外文件')
    return routes


def prepare(source, takes):
    from docx import Document

    original = inventory(source)
    if set(original) != set(ROUTES):
        raise ValueError("Expected the exact 22 course inputs; unknown/missing files: " + str(set(original) ^ set(ROUTES)))
    root = Path(takes) / ("课程材料_" + uuid.uuid4().hex[:8])
    root.mkdir()
    for name in ROUTES:
        raw = (Path(source) / name).read_bytes()
        with (root / name).open("xb") as stream:
            stream.write(raw)
        assert digest(root / name) == original[name]["sha256"]
    notice = Document()
    notice.add_heading("机器人控制系统课程设计：提交与整理要求", level=1)
    notice.add_paragraph("本课程以机器人路径跟踪仿真为主题。本次目录有22个文件，包含课程报告、程序源码、实验结果、配置与运行说明、历史参考及无关个人材料。")
    notice.add_paragraph("必须提交课程设计报告。必须提交程序源码。必须提交实验数据与图表。必须提交配置与运行说明。当前未提供答辩材料，整理成功不等于课程内容审核通过，不新增不存在的文件。")
    notice.add_paragraph("报告v3由本次课程规则指定为最终提交版，v1和v2是历史版本。已有Version工具仅比较三份课程报告以展示证据，不比较其他文件、不自动删除旧版本。")
    notice.add_paragraph("以下22行是唯一的复制操作清单。每行对应一个原文件，只能复制一次；清单结束后不得追加任何复制。不要把提交要求再次展开成第二套操作，不要重复处理同一图片。")
    notice.add_paragraph("输出仅包含课程设计_智能整理结果及其中六个分类文件夹。先形成完整方案，等待一次用户批准，再创建7个目录并复制22份。保留原文件，不移动、不删除、不覆盖。代码、配置及图像按本清单归档，不声称理解未读取的正文。")
    for name in ROUTES:
        notice.add_paragraph('[整理规则] ' + name + " => " + target(Path('.'), name).as_posix())
    notice.add_paragraph("复制清单到此结束：22个源文件、22个唯一目的地、22次复制。验收时核对每个副本SHA-256、六分类数量和原件保持情况。")
    notice.save(root / NOTICE)
    if inventory(source) != original:
        raise ValueError("Original demo changed while preparing")
    baseline = inventory(root)
    destinations = [str(target(root, name)) for name in ROUTES]
    assert len(destinations) == len(set(destinations)) == 22
    return {"workspace": str(root), "baseline": baseline, "original": original,
            "notice_modified_in_copy_only": True, "mapping": [{"filename": n, "source": str(root/n), "target": str(target(root,n)), "reason": "本次课程演示明确规则，非语义分类"} for n in ROUTES]}


def material_input(workspace):
    """Build read-only task context from the workspace scan and requirement document."""
    from fileforge.tools import list_files
    from fileforge.document import read_document

    scan = list_files(workspace=str(workspace), recursive=False)
    notice = read_document(str(Path(workspace) / NOTICE))
    if not scan['success'] or not notice['success']:
        raise ValueError('无法读取工作空间或课程要求')

    files = scan.get('data', {}).get('files') if isinstance(scan.get('data'), dict) else None
    document = (
        notice.get('data', {}).get('document')
        if isinstance(notice.get('data'), dict)
        else None
    )
    if (
        not isinstance(files, list)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get('filename'), str)
            for item in files
        )
        or not isinstance(document, dict)
        or not isinstance(document.get('text'), str)
    ):
        raise ValueError('工作空间扫描结果或课程要求内容无效')

    routes = read_rules(document['text'])
    filenames = [item['filename'] for item in files]
    if len(filenames) != 22 or len(set(filenames)) != 22 or set(filenames) != set(routes):
        raise ValueError('工作空间文件集合与课程整理规则不一致')

    tools = [scan, notice]
    guidance = ('本次任务是依据课程规则复制归档，不是Package材料打包，不要build_package或move_file。'
                '先list_files；只read_document课程要求并extract_requirements；'
                'search_files(query=课程设计报告, extensions=[docx])后read_document({})仅读取3份报告，再compare_versions({})。'
                '不要求对CPP/JSON/CSV/图片做正文分析或match_requirements。随后先连续列出7个create_folder（根+六分类），'
                '再连续22个copy_file；全部29个写操作必须相邻进入一次审批，目录与目的地按课程要求，使用完整绝对路径，'
                '禁止占位路径/删除/覆盖。计划以第22个copy_file结束，不要显式规划verify_result。'
                '项目TaskService在批准的操作结束后已经自动执行源/目标SHA-256验证并追加真实verify_result结果；'
                '不能发明任务ID或重复执行带未知任务ID的验证步骤。'
                '每步description不超过8个汉字。输出前核对：源集合等于Scanner的22个文件，各一次，不能重复。'
                '每条整理规则只产生一个copy_file，22条之后禁止追加复制。全部写操作必须恰好7个create_folder和22个copy_file。')
    prompt_context = (
        '以下为同一Workspace的现有Scanner和read_document真实读取的输入资料（不是执行结果）：\n'
        + json.dumps(tools, ensure_ascii=False)
        + '\n\n'
        + guidance
    )
    return {"tool_inputs": tools, "prompt_context": prompt_context}


def _single_approval_write_batch(steps):
    """Return whether all 29 file-changing steps form one contiguous batch."""
    if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
        return False
    positions = [index for index, step in enumerate(steps) if step.get('risk') == 'medium']
    expected = ['create_folder'] * 7 + ['copy_file'] * 22
    return (
        len(positions) == len(expected)
        and positions == list(range(positions[0], positions[0] + len(expected)))
        and [steps[index].get('tool') for index in positions] == expected
        and all(steps[index].get('status') == 'completed' for index in positions)
    )


def selected_workspace(raw):
    """Explicit user selection only; never fall back to a prepared/default path."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('请先选择有效工作空间')
    root = Path(raw.strip()).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('工作空间必须是存在的绝对目录')
    if root.is_symlink() or getattr(root.lstat(), 'st_file_attributes', 0) & 0x400:
        raise ValueError('不接受符号链接或reparse point工作空间')
    return root.resolve()


def audit(service, tid, records):
    snapshot = service.snapshot(tid)
    root = Path(snapshot['task']['workspace'])
    record = records[str(root)]
    if snapshot['task']['status'] != 'completed':
        raise ValueError("Task is not completed; no successful audit")

    report = service.report(tid)
    results = snapshot.get('results', [])
    notice_result = next(
        (
            result for result in results
            if result.get('tool') == 'read_document'
            and result.get('success')
            and isinstance(result.get('data'), dict)
            and isinstance(result['data'].get('document'), dict)
            and result['data']['document'].get('filename') == NOTICE
        ),
        None,
    )
    if notice_result is None:
        raise ValueError('已完成任务没有读取课程要求文档的记录')

    routes = read_rules(notice_result['data']['document']['text'])
    if set(routes) != set(record['baseline']):
        raise ValueError('实际读取的整理规则与源文件集合不一致')

    pairs = [
        {
            "filename": name,
            "source_sha256": digest(root / name),
            "target_sha256": digest(target(root, name, routes)),
            "approved_demo_baseline_sha256": record['baseline'][name]['sha256'],
        }
        for name in record['baseline']
    ]
    output_root = root / OUTPUT
    actual = {
        str(path.relative_to(output_root))
        for path in output_root.rglob('*')
        if path.is_file()
    }
    expected = {
        str(target(root, name, routes).relative_to(output_root))
        for name in routes
    }
    steps = snapshot['plan'].get('steps', [])
    checks = {
        "all_22_copies_equal": all(
            item['source_sha256'] == item['target_sha256'] == item['approved_demo_baseline_sha256']
            for item in pairs
        ),
        "source_22_unchanged": inventory(root) == record['baseline'],
        "exact_output_22": actual == expected and len(actual) == 22,
        "all_tool_results_success": bool(results)
        and all(result.get('success') is True for result in results),
        "create_folder_count_7": sum(
            result.get('tool') == 'create_folder' for result in results
        ) == 7,
        "copy_tool_count_22": sum(
            result.get('tool') == 'copy_file' for result in results
        ) == 22,
        "single_approval_write_batch": _single_approval_write_batch(steps),
        "six_exact_categories": {
            path.name for path in output_root.iterdir() if path.is_dir()
        } == set(routes.values()),
        "plan_uses_read_rules": all(
            Path(step['arguments']['destination'])
            == target(root, Path(step['arguments']['source']).name, routes)
            for step in steps
            if step.get('tool') == 'copy_file'
        ),
        "backend_sha_verification": bool(results)
        and results[-1].get('tool') == 'verify_result'
        and results[-1].get('success') is True
        and isinstance(results[-1].get('data'), dict)
        and results[-1]['data'].get('passed') is True,
    }
    return {
        "status": "controlled_pass" if all(checks.values()) else "failed",
        "checks": checks,
        "copies": pairs,
        "snapshot": snapshot,
        "final_report": report,
        "disclosure": "现有LLM Planner根据实际读取的课程规则规划；归档不等于内容审核。所有源件保留。",
        "output": str(output_root),
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='NEW absolute directory, never reused/deleted')
    parser.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--backend-url',required=True,help='Existing real Agent HTTP service, e.g. http://127.0.0.1:51851')
    parser.add_argument('--port',type=int,default=0,help='Optional fixed loopback port; occupied ports are never taken over')
    args=parser.parse_args()
    if not 0 <= args.port <= 65535:parser.error('port must be between 0 and 65535')
    if not args.root.is_absolute() or args.root.exists():parser.error('root must be a NEW absolute directory')
    args.root.mkdir(); evidence=args.root/'evidence';evidence.mkdir()
    sys.path.insert(0,str(args.code_root/'src'))
    from fastapi import Request,HTTPException
    from fastapi.responses import HTMLResponse
    from fileforge.api.server import app
    import httpx
    from urllib.parse import urlsplit
    import uvicorn
    backend=args.backend_url.rstrip('/')
    parsed=urlsplit(backend)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.username or parsed.password or parsed.path or parsed.query:
        parser.error('Use an explicit loopback Agent HTTP origin')
    records={}; token=secrets.token_urlsafe(24)
    class ReadOnlyRemoteEvidence:
        def get(self,path):
            with httpx.Client(trust_env=False,timeout=20) as client:
                response=client.get(backend+path);response.raise_for_status();return response.json()
        def snapshot(self,tid):return self.get('/api/agent/tasks/'+tid)
        def report(self,tid):return self.get('/api/agent/tasks/'+tid+'/report')
    service=ReadOnlyRemoteEvidence()
    @app.get('/course-workspace',response_class=HTMLResponse)
    @app.get('/demo/course22',response_class=HTMLResponse)
    def page():
        return Path(__file__).with_name('course22.html').read_text(encoding='utf-8').replace('__DEMO_TOKEN__',token)
    @app.get('/demo/course22/context')
    def context():return {"goal":GOAL,"backend_url":backend,"disclosure":"Existing real Planner receives actual read-only material context; no default workspace or fixed plan"}
    @app.post('/demo/course22/material-input')
    async def inputs(request:Request):
        if request.headers.get('x-demo-token')!=token:raise HTTPException(403,'Local Demo token required')
        try:
            body=await request.json();root=selected_workspace(body.get('workspace'))
            before=inventory(root)
            if (root/OUTPUT).exists():raise ValueError('该目录已存在整理结果，请选择尚未整理的副本；不会覆盖已有结果')
            value=material_input(root)
            if inventory(root)!=before:raise ValueError('读取期间源文件发生变化')
            evidence_id=secrets.token_hex(16)
            records[evidence_id]={"workspace":str(root),"baseline":before}
            (evidence/(evidence_id+'-material-input.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            return {"workspace":str(root),"evidence_id":evidence_id,"prompt_context":value['prompt_context']}
        except (ValueError,OSError) as exc:raise HTTPException(400,str(exc))
    @app.get('/demo/course22/audit/{tid}')
    def check(tid:str,evidence_id:str):
        try:
            record=records[evidence_id]
            result=audit(service,tid,{record['workspace']:record})
            p=evidence/(tid+'.json')
            if not p.exists():p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            return result
        except (KeyError,ValueError,OSError) as exc:raise HTTPException(409,str(exc))
    @app.get('/demo/course22/browser.js')
    def browser_script():
        from fastapi.responses import Response
        return Response(Path(__file__).with_name('course22-browser.js').read_text(encoding='utf-8'),media_type='application/javascript')
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1) if os.name=='nt' else None
    listener.bind(('127.0.0.1',args.port));listener.listen(socket.SOMAXCONN)
    port=listener.getsockname()[1]
    manifest={"url":f'http://127.0.0.1:{port}/course-workspace',"root":str(args.root),"code_root":str(args.code_root),"backend_url":backend,"evidence":str(evidence),"mode":"Existing real llm Planner + actual material context; NO fixed planner or executor override"}
    (args.root/'server.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(manifest,ensure_ascii=True),flush=True)
    try:uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='info')).run(sockets=[listener])
    finally:listener.close()


if __name__=='__main__':main()
