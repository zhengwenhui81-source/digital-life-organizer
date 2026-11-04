"""Read-only organization inputs derived from the selected workspace.

This module does not classify files, manufacture requirements, or execute plans.
Explicit routing lines are optional user input; otherwise the planner receives
observed documents and must ground decisions in them and the user's goal.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

_READABLE = {'.txt', '.pdf', '.docx', '.xlsx'}
_REQUIREMENT_HINTS = ('要求', '规则', '通知', 'requirement', 'instruction', 'notice', 'rules')
_MAX_READS = 10


def _component(value: str) -> bool:
    return bool(value) and value not in {'.', '..'} and not any(
        c in value for c in '/\\:<>"|?*'
    ) and not any(ord(c) < 32 for c in value) and not value.endswith((' ', '.')) and (
        value.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
            *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    )


def parse_routes(text: str, filenames: list[str]) -> dict[str, str]:
    """Validate optional flat-input routing lines, without a fixture whitelist.

Targets have the form output/category/original-name, relative to the workspace.
An explicit list must cover the scanned set exactly; partial lists are ambiguous.
"""
    routes = {}
    destinations = set()
    roots = set()
    source_keys = [name.casefold() for name in filenames]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError('源文件名存在跨平台大小写冲突')
    for line in text.splitlines():
        if not line.startswith('[整理规则]'):
            continue
        pair = line.removeprefix('[整理规则] ').split(' => ')
        if len(pair) != 2:
            raise ValueError('整理规则格式不完整')
        name, raw = pair
        parts = raw.replace('\\', '/').split('/')
        if (name in routes or not _component(name) or len(parts) != 3
                or not all(_component(p) for p in parts) or parts[-1] != name):
            raise ValueError('整理规则重复或目标路径非法')
        target = '/'.join(parts)
        if target.casefold() in destinations:
            raise ValueError('整理规则目标存在大小写冲突')
        destinations.add(target.casefold())
        roots.add(parts[0])
        routes[name] = target
    if routes and (set(routes) != set(filenames) or len(roots) != 1):
        raise ValueError('整理规则必须与实际文件集合一致并使用一个输出目录')
    if roots and next(iter(roots)).casefold() in source_keys:
        raise ValueError('输出目录与源文件冲突')
    categories = {PurePosixPath(p).parts[1] for p in routes.values()}
    if len({c.casefold() for c in categories}) != len(categories):
        raise ValueError('分类目录存在大小写冲突')
    return routes


def organization_input(workspace: str | Path) -> dict:
    from fileforge.tools import list_files
    from fileforge.document import read_document

    root = Path(workspace).resolve(strict=True)
    scan = list_files(workspace=str(root), recursive=False)
    if not scan.get('success'):
        raise ValueError('无法扫描工作空间')
    files = scan.get('data', {}).get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('工作空间没有可整理文件')
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise ValueError('扫描结果无效')
        path = Path(item['path'])
        if (path.parent != root or path.name != item.get('filename')
                or path.is_symlink() or path.resolve() != path
                or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('输入必须是工作空间内的普通文件')
    names = [item['filename'] for item in files]
    readable = [item for item in files if Path(item['path']).suffix.lower() in _READABLE]
    # Names prioritize candidate reads only; they do not establish document roles.
    hinted = [item for item in readable if any(
        word in item['filename'].casefold() for word in _REQUIREMENT_HINTS)]
    candidates = hinted or readable
    if len(candidates) > _MAX_READS:
        raise ValueError('候选文档超过10份，请缩小工作空间或使用交互任务分批分析')
    reads = []
    for item in candidates:
        result = read_document(item['path'])
        if not result.get('success'):
            raise ValueError('无法读取文档：' + item['filename'])
        document = result.get('data', {}).get('document')
        if not isinstance(document, dict) or not isinstance(document.get('text'), str):
            raise ValueError('文档读取结果无效')
        reads.append(result)
    rules_text = '\n'.join(r['data']['document']['text'] for r in reads)
    routes = parse_routes(rules_text, names)
    folders = sorted({str(PurePosixPath(p).parent) for p in routes.values()})
    if routes:
        output = PurePosixPath(next(iter(routes.values()))).parts[0]
        if (root / output).exists():
            raise ValueError('输出目录已存在；不会覆盖已有结果')
        folders.insert(0, output)
    guidance = (
        f'实际扫描到{len(files)}份文件，以实际扫描集合为准。'
        '这是复制归档任务；不调用build_package，不移动、删除或覆盖。'
        '以下资料仅供规划，不是本任务已执行的结果。先list_files并实际读取相关要求文档，再分析。'
        '按实际文档内容决定是否extract_requirements、比较哪些相关版本；无相关版本时不强行比较。'
        '显式规则是用户要求，不是自主分类结果；无规则时依据用户目标和已读取证据提出分类，'
        '不能根据未读取正文声称理解文件，不得默认某个版本就是最终版。'
        '不确定时保留原件，不编造缺项或分类结论。'
        'read_document仅支持TXT/PDF/DOCX/XLSX，自动读取单批至多10份。'
        '先完成读取和分析，再连续安排全部create_folder及copy_file进入审批；'
        '每个源文件至多复制一次，使用完整绝对路径，不使用占位路径。'
        'TaskService在批准执行后自动进行SHA-256验证，不显式规划verify_result。'
        '每步description不超过8个汉字。'
    )
    if routes:
        guidance += (f'本次实际规则对应{len(folders)}个目录和{len(routes)}次复制；'
                     '严格按文档规则生成唯一复制清单，不追加第二套操作。')
    inputs = [scan, *reads]
    return {'tool_inputs': inputs, 'routes': routes, 'folders': folders,
            'prompt_context': '实际扫描和读取的输入资料（不是执行结果）：\n'
            + json.dumps(inputs, ensure_ascii=False) + '\n\n' + guidance}
