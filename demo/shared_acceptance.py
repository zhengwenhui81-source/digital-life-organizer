"""Private acceptance artifacts, not a public API. Default command is read-only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
import urllib.request
import urllib.error

from acceptance_datasets import GOAL, package_rows, classification_rows
from organization_acceptance import guarded, relative, stable_bytes, inventory, digest, json_bytes, UnsafeInput

SCHEMA = 'b-shared-acceptance-v1'
STATES = ('discovered', 'read_success', 'read_failed', 'unsupported', 'not_processed_due_to_limit', 'analyzed', 'needs_confirmation')
TOOLS = ('extract_requirements', 'match_requirements', 'compare_versions', 'detect_conflicts', 'plan_package', 'build_package')
REPO = Path(__file__).resolve().parents[1]


def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()


def environment():
    return {'system': platform.system(), 'python': platform.python_version(), 'head': head(), 'utc': datetime.now(timezone.utc).isoformat()}


def loads(data):
    def pairs(entries):
        out = {}
        for key, value in entries:
            if key in out:
                raise UnsafeInput('Duplicate JSON field')
            out[key] = value
        return out
    def invalid(value):
        raise UnsafeInput('Non-finite JSON number')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def fresh(directory):
    directory = Path(directory)
    if not directory.is_absolute():
        raise UnsafeInput('Specify an absolute NEW test directory')
    guarded(directory.parent)
    directory.mkdir()  # Refuses existing directories, including empty ones.
    return guarded(directory)


def generate(directory):
    root = fresh(directory)
    manifest = {'schema': SCHEMA, 'synthetic': True, 'environment': environment(), 'workflows': {}}
    for workflow, rows in [('package', package_rows()), ('classification', classification_rows())]:
        workspace = root / workflow
        workspace.mkdir()
        gold = []
        for index, item in enumerate(rows, 1):
            item = dict(item)
            data = item.pop('data')
            path = workspace / relative(item['path'])
            path.parent.mkdir(parents=True, exist_ok=True)  # Only the new owned root.
            guarded(path.parent)
            with path.open('xb') as stream:
                stream.write(data)
            # Controlled generation-time chronology, never changed during a run.
            revision = (item.get('expected_version') or {}).get('revision', 1)
            stamp = 1790000000000000000 + revision * 86400000000000
            os.utime(path, ns=(stamp, stamp))
            item['slot'] = index  # Human row index, NOT Document.file_id.
            gold.append(item)
        manifest['workflows'][workflow] = {'files': gold, 'baseline': inventory(workspace),
            'goal': GOAL if workflow == 'package' else '按实际用途整理工作、生活、财务与旅行资料；用途不明请弃权。'}
    manifest['workflows']['package']['expected_filename_absence'] = ['验收意见']
    manifest['workflows']['package']['expected_conflict'] = '报名截止2026-11-01与2026-11-03；不选赢家'
    (root / 'runs').mkdir()
    content = json_bytes(manifest)
    (root / 'gold.json').write_bytes(content)
    table = '# 人工标准答案 · 合成输入，不是实测结果\n\n'
    for workflow, value in manifest['workflows'].items():
        table += '\n## ' + workflow + '\n\n| 文件 | 人工标准答案 |\n| --- | --- |\n'
        table += ''.join('| ' + row['path'] + ' | ' + json.dumps(row, ensure_ascii=False).replace('|', '\\|') + ' |\n' for row in value['files'])
    (root / 'gold.md').write_text(table, encoding='utf-8')
    (root / 'READY.json').write_bytes(json_bytes({'schema': SCHEMA, 'gold_sha256': digest(content)}))
    return {'status': 'prepared_not_tested', 'directory': str(root), 'package_files': 22, 'classification_files': 20, 'llm': 'not_run'}


def baseline(directory):
    root = guarded(directory)
    raw, _ = stable_bytes(root / 'gold.json')
    gold = loads(raw)
    ready = loads(stable_bytes(root / 'READY.json')[0])
    if ready != {'schema': SCHEMA, 'gold_sha256': digest(raw)} or gold.get('schema') != SCHEMA or gold.get('synthetic') is not True:
        raise UnsafeInput('Gold baseline changed or not an owned synthetic dataset')
    for workflow, expected in [('package', 22), ('classification', 20)]:
        value = gold['workflows'][workflow]
        names = [relative(row['path']) for row in value['files']]
        if len(names) != expected or len(set(n.casefold() for n in names)) != expected or set(names) != set(value['baseline']):
            raise UnsafeInput('Incomplete or ambiguous gold manifest')
        definitions = package_rows() if workflow == 'package' else classification_rows()
        expected_rows = [{**{k: v for k, v in row.items() if k != 'data'}, 'slot': i} for i, row in enumerate(definitions, 1)]
        if not same(value['files'], expected_rows):
            raise UnsafeInput('Gold labels differ from the reviewed dataset definition')
    return root, gold, digest(raw)


def validate_snapshot(s, task_id, goal, workspace):
    if not isinstance(s, dict) or type(s.get('results')) is not list or type(s.get('task')) is not dict:
        raise UnsafeInput('Malformed Snapshot')
    task = s['task']
    if any(task.get(k) != v for k, v in [('task_id', task_id), ('user_goal', goal), ('workspace', str(workspace))]):
        raise UnsafeInput('Foreign task, goal or Workspace')
    if task.get('status') not in ('created', 'planning', 'executing', 'verifying', 'awaiting_approval', 'completed', 'failed'):
        raise UnsafeInput('Unknown task status')
    plan = s.get('plan')
    if plan is not None and (type(plan) is not dict or plan.get('task_id') != task_id or plan.get('goal') != goal or type(plan.get('steps')) is not list):
        raise UnsafeInput('Plan identity mismatch')
    for result in s['results']:
        if type(result) is not dict or type(result.get('success')) is not bool or not isinstance(result.get('tool'), str) or type(result.get('message')) is not str or 'data' not in result or 'error' not in result:
            raise UnsafeInput('Invalid ToolResult')
        if result['success'] and (type(result['data']) is not dict or result['error'] is not None) or not result['success'] and (result['data'] is not None or not isinstance(result['error'], str)):
            raise UnsafeInput('Invalid ToolResult envelope')


def read_only_probe(directory, output):
    """Controlled public TaskService runs, real tools, NO approve/decide calls."""
    root, gold, fingerprint = baseline(directory)
    for workflow in ('package', 'classification'):
        if inventory(root / workflow) != gold['workflows'][workflow]['baseline']:
            raise UnsafeInput('Inputs changed; generate a NEW dataset instead of relabeling')
    if Path(output).parent != root / 'runs':
        raise UnsafeInput('Probe evidence directory must be a new child of dataset/runs')
    out = fresh(output)
    from fileforge.agent.service import TaskService
    from fileforge.agent.planner import validate_plan

    observations = []
    workspace = root / 'package'
    def execute(tag, goal, calls):
        allowed = {'list_files', 'search_files', 'read_document', 'compare_versions', 'detect_conflicts', 'extract_requirements', 'match_requirements', 'build_package'}
        if any(tool not in allowed for tool, _ in calls):
            raise UnsafeInput('Write tool forbidden in acceptance probes')
        def planner(task_id, user_goal, scope):
            return validate_plan({'steps': [{'tool': tool, 'description': 'Controlled read-only acceptance', 'arguments': args} for tool, args in calls]}, task_id, user_goal)
        service = TaskService(planner=planner)
        task = service.create(goal, str(workspace))
        service.run(task['task_id'])
        snapshot = service.snapshot(task['task_id'])
        observations.append({'tag': tag, 'task_id': task['task_id'], 'goal': goal, 'snapshot': snapshot})

    execute('batch', GOAL, [('list_files', {'workspace': str(workspace), 'recursive': False}), ('read_document', {}), ('compare_versions', {}), ('extract_requirements', {})])
    # Separate single-file probes are NOT a way to claim the >10 batch passed.
    for row in gold['workflows']['package']['files']:
        name = row['path']
        execute('read:' + name, '只读读取验收文件 ' + name, [('read_document', {'path': str(workspace / name)})])
    calls = [('read_document', {'path': str(workspace / name)}) for name in ('通知_原版.txt', '通知_补充.txt')]
    calls += [('detect_conflicts', {}), ('extract_requirements', {})]
    calls += [('read_document', {'path': str(workspace / name)}) for name in ('结题报告_v1.txt', '结题报告_v2.txt', '实验记录_v1.docx', '实验记录_v2.docx', '费用清单.xlsx', '签字页_待确认.txt')]
    calls += [('compare_versions', {}), ('match_requirements', {}), ('build_package', {})]
    execute('analysis_subset', GOAL, calls)
    record = {'schema': SCHEMA, 'kind': 'controlled_agent_read_only', 'gold_sha256': fingerprint,
              'environment': environment(), 'command': 'python -B demo/shared_acceptance.py probe --directory <dataset> --output <new-run>',
              'observations': observations, 'approvals_sent': 0}
    path = out / 'observations.json'
    path.write_bytes(json_bytes(record))
    return {'status': 'observed_not_e2e', 'artifact': str(path), 'sha256': digest(json_bytes(record)), 'tasks': len(observations), 'llm': 'not_run'}


def capture(directory, output, url, task_id):
    """GET only, loopback only, exact goal/workspace binding before persistence."""
    root, gold, fingerprint = baseline(directory)
    if not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}', url):
        raise UnsafeInput('Only an explicit loopback HTTP port is accepted')
    if not re.fullmatch(r'task_[A-Za-z0-9_]+', task_id):
        raise UnsafeInput('Invalid task ID')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url + '/api/agent/tasks/' + task_id, timeout=15) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise UnsafeInput('Snapshot exceeds capture safety budget')
    snapshot = loads(raw)
    goal = gold['workflows']['package']['goal']
    validate_snapshot(snapshot, task_id, goal, root / 'package')
    report_raw, final_report, report_status = None, None, None
    if snapshot['task']['status'] == 'completed':
        try:
            with opener.open(url + '/api/agent/tasks/' + task_id + '/report', timeout=15) as response:
                report_raw = response.read(16 * 1024 * 1024 + 1)
                report_status = response.status
            if len(report_raw) > 16 * 1024 * 1024:
                raise UnsafeInput('Report exceeds capture safety budget')
            final_report = loads(report_raw)
            if type(final_report) is not dict or final_report.get('task_id') != task_id or final_report.get('status') != 'completed':
                raise UnsafeInput('Foreign or malformed FinalReport')
        except urllib.error.HTTPError as exc:
            report_status = exc.code
        # Do not combine a report with a Snapshot superseded during the GET.
        with opener.open(url + '/api/agent/tasks/' + task_id, timeout=15) as response:
            latest = response.read(16 * 1024 * 1024 + 1)
        if len(latest) > 16 * 1024 * 1024 or not same(loads(latest), snapshot):
            raise UnsafeInput('Snapshot changed during capture; explicitly capture again')
    if Path(output).parent != root / 'runs':
        raise UnsafeInput('Capture output must be a new child of dataset/runs')
    out = fresh(output)
    (out / 'snapshot.raw.json').write_bytes(raw)
    if report_raw is not None:
        (out / 'report.raw.json').write_bytes(report_raw)
    record = {'schema': SCHEMA, 'kind': 'captured_http_unknown_planner', 'gold_sha256': fingerprint,
              'environment': environment(), 'command': 'GET ' + url + '/api/agent/tasks/' + task_id,
              'observations': [{'tag': 'captured', 'task_id': task_id, 'goal': goal, 'snapshot': snapshot, 'final_report': final_report, 'report_http_status': report_status}]}
    (out / 'observations.json').write_bytes(json_bytes(record))
    return {'status': 'captured_not_llm_certified', 'directory': str(out), 'raw_sha256': digest(raw)}


def classification_metrics(gold_rows, decisions):
    """Arithmetic for a full human-reviewed export; NOT a classify_files adapter."""
    names = {r['path'] for r in gold_rows}
    if type(decisions) is not list or any(type(d) is not dict for d in decisions) or len(decisions) != len(names) or {d.get('path') for d in decisions} != names:
        return {'status': 'unverifiable', 'reason': 'Require one actual decision for EVERY gold file; no cherry-picking', 'purpose_accuracy': None, 'purpose_coverage': None}
    gold = {r['path']: r for r in gold_rows}
    for d in decisions:
        row = gold[d['path']]
        if d.get('method') not in ('purpose_from_content', 'file_type_only', 'abstain') or type(d.get('evidence')) is not str or not d['evidence'].strip() or d.get('method') != 'abstain' and type(d.get('label')) is not str:
            return {'status': 'unverifiable', 'purpose_accuracy': None, 'purpose_coverage': None}
    purpose = [d for d in decisions if d['method'] == 'purpose_from_content']
    typed = [d for d in decisions if d['method'] == 'file_type_only']
    correct = sum(d['label'] == gold[d['path']]['human_category'] and 'purpose_from_content' in gold[d['path']]['allowed_methods'] and not gold[d['path']]['must_abstain_purpose'] for d in purpose)
    return {'status': 'arithmetic_only_not_real_classification', 'total': len(names), 'purpose_classified': len(purpose),
            'purpose_correct': correct, 'purpose_accuracy': correct / len(purpose) if purpose else None,
            'purpose_coverage': len(purpose) / len(names), 'type_grouped': len(typed),
            'type_accuracy': sum(d['label'] == gold[d['path']]['human_file_type'] and 'file_type_only' in gold[d['path']]['allowed_methods'] for d in typed) / len(typed) if typed else None,
            'type_coverage': len(typed) / len(names), 'abstained': sum(d['method'] == 'abstain' for d in decisions),
            'target_95_achieved': correct / len(purpose) >= .95 if purpose else None}


def code_fingerprints():
    return {p.relative_to(REPO).as_posix(): digest(stable_bytes(p)[0]) for p in sorted((REPO / 'demo').glob('*acceptance*.py'))}


def check_tools(directory, output):
    root, _, _ = baseline(directory)
    if Path(output).parent != root / 'runs':
        raise UnsafeInput('Test logs must be a new child of dataset/runs')
    out = fresh(output)
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'demo', '-p', 'test_*acceptance*.py', '-v']
    hashes = code_fingerprints()
    try:
        completed = subprocess.run(command, cwd=REPO, capture_output=True, timeout=240)
        log, code = completed.stdout + completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        log, code = (exc.stdout or b'') + (exc.stderr or b'') + b'\nTIMEOUT\n', 124
    count = re.search(rb'Ran (\d+) tests? in ', log)
    record = {'kind': 'command_observation', 'command': command, 'exit_code': code, 'total': int(count[1]) if count else None,
              'environment': environment(), 'log_file': 'tests.log', 'log_sha256': digest(log), 'code_sha256': hashes}
    (out / 'tests.log').write_bytes(log)
    (out / 'test-record.json').write_bytes(json_bytes(record))
    return {'status': 'passed' if code == 0 else 'failed', 'tests': record['total'], 'exit_code': code, 'record': str(out / 'test-record.json')}


def package_bytes(snapshot, workspace, original_files):
    """Read-only byte observations, never approval or a Package-success verdict."""
    results = snapshot['results']
    attempt = next((i for i in range(len(results)-1, -1, -1) if results[i]['tool'] == 'plan_package'), None)
    mapping = snapshot.get('package_execution')
    out = {'status': 'not_run' if mapping is None else 'unverifiable', 'copies': [], 'cleanup_results': None,
           'reason': 'No approved execution mapping' if mapping is None else 'Byte observations do not certify the complete execution/FinalReport'}
    if mapping is None:
        return out
    if attempt is None or not results[attempt]['success']:
        raise UnsafeInput('Execution lacks current successful planning')
    data = results[attempt]['data']
    plan = data.get('plan')
    if type(plan) is not dict or type(mapping) is not dict or plan.get('task') != {k: snapshot['task'][k] for k in ('task_id', 'user_goal', 'workspace')} or mapping.get('plan_id') != plan.get('plan_id') or mapping.get('plan_sha256') != data.get('plan_sha256'):
        raise UnsafeInput('Execution/plan identity mismatch')
    descriptors, links = plan.get('operations'), mapping.get('operation_results')
    if type(descriptors) is not list or type(links) is not list:
        raise UnsafeInput('Invalid execution links')
    previous, stopped = attempt, False
    copied_sources, target_keys = set(), set()
    out['cleanup_results'] = strip_text(mapping.get('cleanup_results'))
    for position, link in enumerate(links):
        if type(link) is not dict or position >= len(descriptors) or type(descriptors[position]) is not dict:
            raise UnsafeInput('Invalid execution step')
        descriptor, index = descriptors[position], link.get('result_index')
        tool = {'create_directory': 'create_folder', 'copy': 'copy_file', 'write_report': 'write_package_report', 'verify': 'verify_result'}.get(descriptor.get('kind'))
        if type(index) is not int or index <= previous or index >= len(results) or link.get('step_id') != descriptor.get('step_id') or results[index]['tool'] != tool:
            raise UnsafeInput('Invalid ordered execution evidence')
        previous = index
        result = results[index]
        if stopped:
            raise UnsafeInput('Post-failure records cannot prove a successful copy')
        if descriptor['kind'] == 'copy':
            selected_index = descriptor.get('selected_file_index')
            if type(selected_index) is not int or selected_index < 0 or selected_index >= len(plan['selected_files']):
                raise UnsafeInput('Invalid selected file index')
            item = plan['selected_files'][selected_index]
            source, target = Path(item['source']['path']), Path(item['target'])
            name = relative(source.relative_to(workspace).as_posix())
            target_name = relative(target.relative_to(workspace).as_posix())
            if name in copied_sources or target_name.casefold() in target_keys or target_name.casefold() in {n.casefold() for n in original_files}:
                raise UnsafeInput('Duplicate copy or preexisting target')
            copied_sources.add(name)
            target_keys.add(target_name.casefold())
            if name not in original_files or item['snapshot']['sha256'] != original_files[name]['sha256']:
                raise UnsafeInput('Frozen source does not match the immutable test baseline')
            if result['success'] and result['data'] != {'source': str(source), 'destination': str(target)}:
                raise UnsafeInput('Copy result mapping mismatch')
            source_raw, _ = stable_bytes(source)
            observed = {'source': name, 'target': target.relative_to(workspace).as_posix(), 'task_id': snapshot['task']['task_id'], 'result_index': index,
                        'tool_success': result['success'], 'original_preserved': digest(source_raw) == original_files[name]['sha256']}
            try:
                raw, _ = stable_bytes(target)
                observed.update(target_exists=True, target_sha256=digest(raw), bytes_match_frozen=digest(raw) == item['snapshot']['sha256'])
            except FileNotFoundError:
                observed.update(target_exists=False, bytes_match_frozen=False)
            out['copies'].append(observed)
        stopped = not result['success'] or tool == 'verify_result' and result['data'].get('passed') is not True
    if stopped or snapshot['task']['status'] == 'failed':
        out['status'] = 'failed'
    return out


def report(directory, evidence=None, tests=None):
    root, gold, fingerprint = baseline(directory)
    rows = {r['path']: {'path': r['path'], 'states': {s: {'state': 'unverifiable', 'evidence': []} for s in STATES}} for r in gold['workflows']['package']['files']}
    result = {'schema': SCHEMA, 'status': 'blocked', 'environment': environment(), 'gold_sha256': fingerprint,
              'dataset': {'package': 22, 'classification': 20, 'synthetic': True, 'legacy_22_template': 'unchanged_pending'},
              'scope': 'Independent read probes and analysis subset; never one 22-file Package run',
              'layers': {'code_exists': {'status': 'observed', 'paths': ['src/fileforge/agent/service.py', 'src/fileforge/package/planning.py']},
                         'automatic_tests': {'status': 'not_run', 'reason': 'No test log attached by this command'},
                         'controlled_windows': {'status': 'not_run'}, 'browser_e2e': {'status': 'not_run'}, 'deepseek': {'status': 'not_run'}},
              'tool_results': [], 'run_outcomes': [], 'issues': [], 'classification': {'status': 'blocked', 'purpose_accuracy': None, 'purpose_coverage': None, 'reason': 'classify_files contract/adapter not frozen; no actual decisions'},
              'package_execution': {'status': 'not_run', 'reason': 'No approved execution evidence'}, 'filesystem': {}}
    for workflow in ('package', 'classification'):
        actual = inventory(root / workflow)
        expected = gold['workflows'][workflow]['baseline']
        changed = [name for name in expected if actual.get(name) != expected[name]]
        result['filesystem'][workflow] = {'status': 'failed' if changed else 'originals_unchanged', 'changed_or_missing': changed, 'unexpected_files': sorted(set(actual) - set(expected)), 'inventory': actual}
        if changed:
            result['status'] = 'failed'
    def confirm(name, state, task_id, index, basis):
        if name in rows and name not in result['filesystem']['package']['changed_or_missing']:
            rows[name]['states'][state]['state'] = 'confirmed'
            rows[name]['states'][state]['evidence'].append({'task_id': task_id, 'result_index': index, 'basis': basis})
    if evidence is not None:
        raw, _ = stable_bytes(evidence)
        record = loads(raw)
        try:
            if record.get('schema') != SCHEMA or record.get('gold_sha256') != fingerprint or record.get('kind') not in ('controlled_agent_read_only', 'captured_http_unknown_planner') or type(record.get('observations')) is not list:
                raise UnsafeInput('Unknown provenance or mismatched gold')
            seen = set()
            for entry in record['observations']:
                if entry['task_id'] in seen:
                    raise UnsafeInput('Duplicate/old task observation; explicitly select ONE current Snapshot per task')
                seen.add(entry['task_id'])
                validate_snapshot(entry['snapshot'], entry['task_id'], entry['goal'], root / 'package')
                expected_goal = '只读读取验收文件 ' + entry['tag'][5:] if entry['tag'].startswith('read:') else GOAL
                if entry['goal'] != expected_goal:
                    raise UnsafeInput('Unexpected experiment goal')
            result['artifact'] = {'sha256': digest(raw), 'kind': record['kind'], 'environment': record.get('environment'), 'command': record.get('command'), 'trust': 'Local capture, not cryptographic server attestation or LLM provenance'}
            if record['kind'] == 'controlled_agent_read_only':
                result['layers']['controlled_windows'] = {'status': 'observed_read_only' if record.get('environment', {}).get('system') == 'Windows' else 'not_windows', 'evidence_sha256': digest(raw)}
            result['layers']['deepseek'] = {'status': 'unverifiable', 'reason': 'Snapshot has no authoritative model/provider evidence; never infer from success'}
            for entry in record['observations']:
                s, tid = entry['snapshot'], entry['task_id']
                if entry.get('final_report') is not None and (type(entry['final_report']) is not dict or entry['final_report'].get('task_id') != tid or entry['final_report'].get('status') != s['task']['status']):
                    raise UnsafeInput('Foreign or stale FinalReport')
                result['run_outcomes'].append({'tag': entry['tag'], 'task_id': tid, 'status': s['task']['status'], 'error': s.get('error'), 'final_report': strip_text(entry.get('final_report')), 'report_http_status': entry.get('report_http_status')})
                reads = {}
                for i, tool in enumerate(s['results']):
                    data = tool['data']
                    if tool['tool'] in ('list_files', 'search_files') and tool['success']:
                        found = data.get('files' if tool['tool'] == 'list_files' else 'matches')
                        if type(found) is not list:
                            raise UnsafeInput('Invalid discovery result')
                        for item in found:
                            if type(item) is dict and type(item.get('path')) is str:
                                try:
                                    name = Path(item['path']).relative_to(root / 'package').as_posix()
                                except ValueError:
                                    raise UnsafeInput('Foreign discovery path')
                                confirm(name, 'discovered', tid, i, 'successful discovery ToolResult path')
                    if tool['tool'] == 'read_document' and tool['success']:
                        doc = data.get('document')
                        if type(doc) is not dict or not isinstance(doc.get('file_id'), str) or not doc['file_id'] or not isinstance(doc.get('text'), str) or type(doc.get('size')) is not int or doc['size'] < 0:
                            raise UnsafeInput('Invalid successful Document')
                        name = Path(doc['path']).relative_to(root / 'package').as_posix()
                        if name not in rows or doc.get('filename') != Path(name).name:
                            raise UnsafeInput('Unknown read identity')
                        if doc['size'] != gold['workflows']['package']['baseline'][name]['size']:
                            raise UnsafeInput('Read evidence size differs from dataset baseline')
                        if doc['file_id'] in reads and (reads[doc['file_id']][0] != name or not same(reads[doc['file_id']][1], doc)):
                            raise UnsafeInput('Contradictory read identity')
                        reads[doc['file_id']] = (name, doc)
                        confirm(name, 'read_success', tid, i, 'successful Document identity/path')
                    if tool['tool'] == 'read_document' and not tool['success']:
                        steps = (s.get('plan') or {}).get('steps', [])
                        # No positional guessing for dynamic expansion or multiple steps.
                        if len(s['results']) == len(steps) == 1 and steps[0].get('tool') == 'read_document' and type(steps[0].get('arguments')) is dict and set(steps[0]['arguments']) == {'path'}:
                            name = Path(steps[0]['arguments']['path']).relative_to(root / 'package').as_posix()
                            confirm(name, 'read_failed', tid, i, 'single explicit path call and sole failed ToolResult')
                    if tool['tool'] in TOOLS:
                        current = not any(later['tool'] == tool['tool'] or later['tool'] == 'read_document' for later in s['results'][i+1:])
                        summary = {'tag': entry['tag'], 'task_id': tid, 'result_index': i, 'tool': tool['tool'], 'success': tool['success'], 'error': tool['error'], 'current_for_file_coverage': current}
                        if tool['success']:
                            for key in ('required_documents', 'matched', 'missing', 'groups', 'conflicts'):
                                if key in data:
                                    summary[key] = strip_text(data[key])
                            if tool['tool'] == 'plan_package':
                                plan = data.get('plan')
                                if type(plan) is dict and plan.get('task') == {k: s['task'][k] for k in ('task_id', 'user_goal', 'workspace')}:
                                    summary['plan_id'] = plan.get('plan_id')
                                    summary['plan_sha256'] = data.get('plan_sha256')
                                    summary['destination'] = plan.get('destination')
                                    summary['selected_files'] = strip_text(plan.get('selected_files'))
                                    summary['operations'] = plan.get('operations')
                                    summary['missing'] = plan.get('missing')
                                    summary['unresolved'] = strip_text(plan.get('unresolved'))
                                    if s.get('package_execution') is None:
                                        result['package_execution'] = {'status': 'not_run', 'reason': 'Frozen preview only; no execution mapping', 'task_id': tid}
                                    for u in plan.get('unresolved', []) if current else []:
                                        source_index = u.get('source_result_index')
                                        slot = plan.get('analysis', {}).get(u.get('source_tool'))
                                        if u.get('documents') and (type(source_index) is not int or not 0 <= source_index < i or s['results'][source_index]['success'] is not True or s['results'][source_index]['tool'] != u.get('source_tool') or type(slot) is not dict or slot.get('result_index') != source_index or not same(slot.get('result'), s['results'][source_index])):
                                            raise UnsafeInput('Frozen unresolved source is invalid')
                                        for doc in u.get('documents', []):
                                            known = reads.get(doc.get('file_id'))
                                            if known and known[1]['path'] == doc.get('path'):
                                                confirm(known[0], 'needs_confirmation', tid, i, 'frozen unresolved document reference')
                        result['tool_results'].append(summary)
                        if current and tool['success'] and tool['tool'] in ('compare_versions', 'match_requirements'):
                            groups = data.get('groups' if tool['tool'] == 'compare_versions' else 'matched', [])
                            for group in groups:
                                for doc in group.get('documents', []):
                                    known = reads.get(doc.get('file_id'))
                                    full_match = tool['tool'] != 'compare_versions' or known and same(doc, known[1])
                                    if known and full_match and doc.get('path') == known[1]['path'] and doc.get('filename') == known[1]['filename']:
                                        confirm(known[0], 'analyzed', tid, i, 'explicit ' + tool['tool'] + ' document membership (not semantic approval)')
                if s.get('error'):
                    result['issues'].append({'task_id': tid, 'tag': entry['tag'], 'reason': s['error']})
                if s.get('package_execution') is not None:
                    result['package_execution'] = package_bytes(s, root / 'package', gold['workflows']['package']['baseline'])
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            result['issues'].append({'reason': 'Evidence rejected: ' + type(exc).__name__})
            # Transactional fail-closed: no partial coverage survives bad evidence.
            for row in rows.values():
                row['states'] = {s: {'state': 'unverifiable', 'evidence': []} for s in STATES}
            result['tool_results'] = []
            result['run_outcomes'] = []
            result['package_execution'] = {'status': 'unverifiable'}
    result['layers']['external_blocked'] = {'status': 'blocked', 'reasons': ['classify_files schema/adapter not frozen', *[i['reason'] for i in result['issues'] if i.get('tag') in ('batch', 'analysis_subset', 'captured')]]}
    if tests is not None:
        try:
            test_bytes, _ = stable_bytes(tests)
            record = loads(test_bytes)
            log = stable_bytes(Path(tests).parent / relative(record['log_file']))[0]
            count = re.search(rb'Ran (\d+) tests? in ', log)
            if record.get('kind') != 'command_observation' or type(record.get('exit_code')) is not int or record.get('log_sha256') != digest(log) or set(record.get('code_sha256', {})) != set(code_fingerprints()):
                raise UnsafeInput('Test log does not prove the claimed successful run')
            for name, expected_hash in record['code_sha256'].items():
                if digest(stable_bytes(REPO / relative(name))[0]) != expected_hash:
                    raise UnsafeInput('Tested code has changed')
            passed = record['exit_code'] == 0 and count and int(count[1]) == record['total'] and log.rstrip().endswith(b'OK')
            result['layers']['automatic_tests'] = {'status': 'passed' if passed else 'failed', 'tests': record['total'], 'exit_code': record['exit_code'], 'command': record['command'], 'environment': record['environment'], 'record_sha256': digest(test_bytes), 'log_sha256': digest(log), 'trust': 'Local recorded command, not remote attestation'}
        except (OSError, ValueError, TypeError, KeyError):
            result['layers']['automatic_tests'] = {'status': 'unverifiable', 'reason': 'Missing/failed/modified test evidence'}
    result['files'] = list(rows.values())
    result['coverage'] = {state: {'confirmed': sum(row['states'][state]['state'] == 'confirmed' for row in rows.values()), 'denominator': 22, 'meaning': 'confirmed lower bound, NOT complete task coverage'} for state in STATES}
    result['limitations'] = ['No per-file skipped/limit/unsupported authority field: retain unverifiable', 'Read-failed path bound only for a single explicit read step/result', 'Independent tasks never form one Package execution', 'No write or approval is performed by report/probe']
    return result


def strip_text(value):
    if isinstance(value, list):
        return [strip_text(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_text(v) for k, v in value.items() if k not in ('text', 'content', 'metadata')}
    return value


def markdown(value):
    text = '# 统一验收证据报告\n\n'
    text += '总体：' + value.get('status', 'unverifiable') + '。生成数据、只读探针、浏览器、LLM分开记录。\n\n'
    text += '```json\n' + json.dumps({k: v for k, v in value.items() if k != 'files'}, ensure_ascii=False, indent=2) + '\n```\n\n'
    if 'files' in value:
        text += '| 文件 | ' + ' | '.join(STATES) + ' |\n| --- | ' + ' | '.join('---' for _ in STATES) + ' |\n'
        for row in value['files']:
            text += '| ' + row['path'] + ' | ' + ' | '.join(row['states'][s]['state'] for s in STATES) + ' |\n'
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    for command in ('generate', 'report', 'probe', 'capture', 'check-tools'):
        p = sub.add_parser(command)
        p.add_argument('--directory', required=True, type=Path)
        if command in ('probe', 'capture', 'check-tools'):
            p.add_argument('--output', required=True, type=Path)
        if command == 'capture':
            p.add_argument('--url', required=True)
            p.add_argument('--task-id', required=True)
        if command == 'report':
            p.add_argument('--evidence', type=Path)
            p.add_argument('--tests', type=Path)
            p.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args(argv)
    try:
        command = args.command or 'report'
        if not args.command:
            parser.error('Use report --directory for read-only inspection; generation is opt-in')
        value = generate(args.directory) if command == 'generate' else read_only_probe(args.directory, args.output) if command == 'probe' else capture(args.directory, args.output, args.url, args.task_id) if command == 'capture' else check_tools(args.directory, args.output) if command == 'check-tools' else report(args.directory, args.evidence, args.tests)
        print(markdown(value) if getattr(args, 'format', 'json') == 'markdown' else json.dumps(value, ensure_ascii=True, indent=2))
        return 1 if value.get('status') == 'failed' else 2 if command == 'report' else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'unverifiable', 'reason': type(exc).__name__ + ': ' + str(exc)}, ensure_ascii=True))
        return 2 if args.command == 'report' else 1


if __name__ == '__main__':
    sys.exit(main())
