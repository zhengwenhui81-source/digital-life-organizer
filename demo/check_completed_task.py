"""Read-only audit of a real browser acceptance and its current filesystem/API."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def check_bytes(workspace, baseline, copies):
    verified = []
    for name, expected in baseline.items():
        source = workspace / name
        stat = source.stat()
        assert source.is_file(), 'Original missing'
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected['sha256'], 'Original bytes changed'
        assert str(stat.st_size) == expected['size'], 'Original size changed'
        assert str(stat.st_mtime_ns) == expected['mtime_ns'], 'Original timestamp changed'
    targets = set()
    for operation in copies:
        source = Path(operation['data']['source']).resolve()
        destination = Path(operation['data']['destination']).resolve()
        relative = destination.relative_to(workspace.resolve())
        assert relative.parts[0] == '整理结果', 'Unexpected output root'
        assert source.parent == workspace.resolve() and source.name in baseline, 'Unknown source'
        assert destination not in targets, 'Duplicate destination'
        targets.add(destination)
        assert destination.is_file(), 'Destination missing'
        data = destination.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == baseline[source.name]['sha256'], 'Copied bytes differ'
        verified.append({'source': str(source), 'destination': str(destination), 'sha256':digest, 'bytes':len(data)})
    disk = {p.resolve() for p in (workspace / '整理结果').rglob('*') if p.is_file()}
    assert disk == targets, 'Unexpected or missing output files'
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    baseline = json.loads((evidence / 'baseline.json').read_text(encoding='utf-8'))
    record = json.loads((evidence / 'acceptance.json').read_text(encoding='utf-8'))
    tid = record['task_id']
    assert tid.startswith('task_') and '/' not in tid
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(suffix):
        with opener.open('http://127.0.0.1:8000/api/agent/tasks/' + tid + suffix, timeout=15) as response:
            return json.load(response)
    snapshot, report = get(''), get('/report')
    assert snapshot['task']['task_id'] == report['task_id'] == tid
    assert snapshot['task']['status'] == report['status'] == 'completed'
    assert report == record['report'], 'Current report differs from captured report'
    results = snapshot['results']
    assert all(result['success'] is True for result in results)
    assert snapshot['pending_operations'] == [] and snapshot['preview_id'] is None
    calls = record['http']
    assert sum(r['method']=='POST' and r['path']=='/api/agent/tasks' for r in calls)==1
    assert any(r['method']=='POST' and r['path']==f'/api/agent/tasks/{tid}/answers' for r in calls)
    approvals = [r for r in calls if r['method']=='POST' and r['path'].endswith('/approve')]
    assert len(approvals)==1 and approvals[0]['path']==f'/api/agent/tasks/{tid}/approve'
    frozen = json.loads((evidence / 'frozen-preview.json').read_text(encoding='utf-8'))
    assert json.loads(approvals[0]['body'])['preview_id']==frozen['snapshot']['preview_id']
    states = {item['task']['status'] for item in record['history'] if item.get('task')}
    assert {'awaiting_clarification','awaiting_approval','completed'} <= states
    assert {item['task']['task_id'] for item in record['history'] if item.get('task')}=={tid}
    workspace = Path(baseline['workspace']).resolve()
    assert Path(snapshot['task']['workspace']).resolve()==workspace
    reads = [r['data']['document'] for r in results if r['tool']=='read_document']
    assert len(reads)==len(baseline['files'])
    for doc in reads:
        source=Path(doc['path'])
        assert source.parent.resolve()==workspace
        assert doc['text'].strip()==source.read_text(encoding='utf-8').strip(), 'Read body differs'
    assert any(r['tool']=='compare_versions' for r in results)
    assert all(event['status']=='responded' and event['provider_host']=='api.deepseek.com' for event in record['model_events'])
    assert record['model_events'], 'No real Planner response evidence'
    copies = [r for r in report['operations'] if r['tool']=='copy_file']
    assert len(copies)==3
    assert {Path(r['data']['source']).name for r in copies}=={'附件B.txt','记录甲.txt','清单乙.txt'}
    verified = check_bytes(workspace, baseline['files'], copies)
    assert results[-1]['tool']=='verify_result' and results[-1]['data']['passed'] is True
    assert len(results[-1]['data']['checks'])==len(report['operations'])
    assert all(check['passed'] is True for check in results[-1]['data']['checks'])
    print(json.dumps({'status':'passed','task_id':tid,'workspace':str(workspace),'model_calls':len(record['model_events']),
        'documents_read':len(reads),'same_task_continuation':True,'approval_requests':1,'directories_created':sum(r['tool']=='create_folder' for r in report['operations']),
        'copies_verified':verified,'originals_unchanged':True,'server_verified':True,'report_matches_current_api':True,'read_only_audit':True},ensure_ascii=False))


if __name__=='__main__':
    main()
