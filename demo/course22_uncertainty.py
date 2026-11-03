"""Separate weak-evidence experiment. Never imports the successful Demo guidance.

prepare copies inputs and edits only the copied course notice using OOXML.
run makes at most one create-task request, never approves/retries a task.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

NOTICE = '课程设计_提交要求.docx'
PARAGRAPHS = [
    '移动机器人课程设计提交要求',
    '本课程研究二维移动机器人路径跟踪。提交材料应使教师能够审阅模型、控制方法、实验过程和结果，并按说明复现程序。',
    '需要提供课程设计报告，说明运动学模型、控制算法、实验参数、轨迹及误差分析、局限性和复现步骤。报告定稿须由提交人确认；修改编号和保存时间本身不表示已经审核或决定提交。',
    '需要提供能够配合运行的程序源代码、必要配置、实验数据与图表，以及编译运行和实验说明。应保留材料间的依赖关系，不应仅凭文件扩展名认定内容完整或可复现。',
    '工作目录保留了迭代过程，未完整登记所有旧程序是否仍为当前实验所需，也未登记每份过程记录是否应随正式材料提交。无法确定用途时应保留原件，由提交人确认处理方式。',
    '内部讨论和自查材料仅作参考，不自动等同于教师的正式提交要求；答辩材料是否需要单独提交，应以教师后续通知为准。',
    '整理时保留全部原始文件，不移动、不删除、不覆盖。先展示有依据的整理建议与尚未确定的事项，取得用户确认和操作审批后才能创建目录并复制。未确定的材料不能擅自标记为已确定用途或审核通过。',
]
GOAL = ('请根据课程设计提交要求分析当前工作空间并提出复制整理方案，识别报告、程序、配置、实验材料及它们的关联。'
        '请使用有依据的版本和需求分析，不把编号最新等同于已确认定稿。证据不足时请指出具体文件、原因与可选处理方式，'
        '先询问我，得到回答后再确定这些文件的去向。不要强制把所有文件分类完毕。保留原件，实际创建目录或复制必须先经审批。')


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def inventory(root):
    result = {}
    for p in Path(root).iterdir():
        s = p.lstat()
        if p.is_symlink() or getattr(s, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Refuse links/reparse points')
        if p.is_file():
            result[p.name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                              'size': s.st_size, 'mtime_ns': str(s.st_mtime_ns)}
    return result


def prepare(source, root):
    before = inventory(source)
    if len(before) != 22 or NOTICE not in before:
        raise ValueError('Expected 22 source files including course notice')
    root.mkdir()  # exclusive, never replace a prior experiment
    workspace = root / 'workspace'
    workspace.mkdir()
    for name in before:
        shutil.copy2(source / name, workspace / name)
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    ET.register_namespace('w', ns)
    document = ET.Element('{%s}document' % ns)
    body = ET.SubElement(document, '{%s}body' % ns)
    with zipfile.ZipFile(source / NOTICE) as original:
        old = ET.fromstring(original.read('word/document.xml'))
        section = old.find('.//{%s}sectPr' % ns)
        for index, text in enumerate(PARAGRAPHS):
            p = ET.SubElement(body, '{%s}p' % ns)
            if index == 0:
                prop = ET.SubElement(p, '{%s}pPr' % ns)
                ET.SubElement(prop, '{%s}pStyle' % ns, {'{%s}val' % ns: 'Title'})
            run = ET.SubElement(p, '{%s}r' % ns)
            ET.SubElement(run, '{%s}t' % ns).text = text
        if section is not None:
            body.append(section)
        blobs = [(info, original.read(info.filename)) for info in original.infolist()]
    with zipfile.ZipFile(workspace / NOTICE, 'w', zipfile.ZIP_DEFLATED) as edited:
        for info, blob in blobs:
            edited.writestr(info, ET.tostring(document, encoding='utf-8', xml_declaration=True)
                            if info.filename == 'word/document.xml' else blob)
    after = inventory(workspace)
    assert [n for n in before if before[n]['sha256'] != after[n]['sha256']] == [NOTICE]
    assert inventory(source) == before
    write(root / 'baseline.json', {'source': str(source), 'workspace': str(workspace),
                                   'original': before, 'experiment': after,
                                   'changed_files': [NOTICE], 'notice_paragraphs': PARAGRAPHS})
    print(str(workspace), flush=True)


def run(root, code_root, backend):
    import httpx
    sys.path.insert(0, str(code_root / 'src'))
    from fileforge.tools import list_files
    from fileforge.document import read_document
    baseline = json.loads((root / 'baseline.json').read_text(encoding='utf-8'))
    workspace = Path(baseline['workspace'])
    assert inventory(workspace) == baseline['experiment']
    assert inventory(Path(baseline['source'])) == baseline['original']
    scan = list_files(workspace=str(workspace), recursive=False)
    notice = read_document(str(workspace / NOTICE))
    if not scan['success'] or not notice['success']:
        raise ValueError('Actual scan/notice read failed; no model request')
    text = notice['data']['document']['text']
    assert '[整理规则]' not in text and '=>' not in text
    inputs = [scan, notice]
    write(root / 'actual-inputs.json', inputs)
    # No successful-demo material_input(), ROUTES, forced counts or filename mapping.
    payload = {'workspace': str(workspace), 'user_goal': GOAL +
               '\n以下是该目录真实扫描和课程要求读取所得输入资料，不是本Task已执行的结果：\n' +
               json.dumps(inputs, ensure_ascii=False)}
    write(root / 'request.json', payload)
    write(root / 'once-attempt.json', {'created_at': datetime.now(timezone.utc).isoformat(),
                                      'backend': backend, 'automatic_retry': False})
    trace, snapshots, final = [], [], None
    with httpx.Client(trust_env=False, timeout=30) as client:
        def request(method, path, **kwargs):
            start = time.monotonic()
            response = client.request(method, backend + path, **kwargs)
            trace.append({'time': datetime.now(timezone.utc).isoformat(), 'method': method,
                          'path': path, 'status': response.status_code,
                          'duration_ms': (time.monotonic() - start) * 1000})
            return response
        try:
            response = request('POST', '/api/agent/tasks', json=payload)
            write(root / 'create-response.json', {'status': response.status_code, 'body': response.json()})
            response.raise_for_status()
            tid = response.json()['task_id']
            write(root / 'task-id.json', {'task_id': tid})
            for _ in range(180):
                response = request('GET', '/api/agent/tasks/' + tid)
                response.raise_for_status()
                final = response.json()
                snapshots.append({'time': datetime.now(timezone.utc).isoformat(), 'snapshot': final})
                if final['task']['status'] in {'awaiting_approval', 'failed', 'completed'}:
                    break
                time.sleep(1)
            write(root / 'snapshot.json', final)
            response = request('GET', '/api/agent/tasks/' + tid + '/report')
            write(root / 'report-response.json', {'status': response.status_code, 'body': response.json()})
        finally:
            write(root / 'http-trace.json', trace)
            write(root / 'snapshots.json', snapshots)
            check = {'experiment_unchanged': inventory(workspace) == baseline['experiment'],
                     'original_unchanged': inventory(Path(baseline['source'])) == baseline['original'],
                     'directories_created': [p.name for p in workspace.iterdir() if p.is_dir()],
                     'approve_requests': 0, 'task_create_requests': sum(r['method']=='POST' for r in trace)}
            write(root / 'final-file-check.json', check)
    print(json.dumps({'task_id': tid, 'status': final['task']['status'], 'error': final.get('error'),
                      'tool_counts': dict(Counter(r['tool'] for r in final['results'])),
                      'integrity': check}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--source', type=Path)
    p.add_argument('--code-root', type=Path)
    p.add_argument('--backend', default='http://127.0.0.1:51851')
    args = p.parse_args()
    if args.action == 'prepare':
        prepare(args.source, args.root)
    else:
        if args.backend != 'http://127.0.0.1:51851':
            p.error('This experiment is restricted to the existing authorized service')
        run(args.root, args.code_root, args.backend)
