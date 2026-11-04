"""Unknown-workspace regression; controlled planners do not measure LLM accuracy."""
import json
from pathlib import Path
import sys

import pytest

from fileforge.agent.organization_context import organization_input, parse_routes
from fileforge.agent.planner import plan_task, validate_plan
from fileforge.agent.service import TaskService, TaskConflict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'demo'))
from course22_demo import audit, inventory


def fixture(root, count):
    names = ['提交规则.txt'] + [f'sensor_{i}.csv' for i in range(count)]
    routes = {n: f'整理归档/{"说明" if n.endswith("txt") else "测量"}/{n}' for n in names}
    for name in names:
        (root / name).write_text('measured values\n1,2,3', encoding='utf-8')
    (root / names[0]).write_text('\n'.join('[整理规则] ' + n + ' => ' + p
        for n, p in routes.items()), encoding='utf-8')
    return routes


@pytest.mark.parametrize('count', [1, 4, 12, 24])
def test_variable_inputs_use_real_approval_copy_and_audit(tmp_path, count):
    expected = fixture(tmp_path, count)
    before = inventory(tmp_path)
    context = organization_input(tmp_path)
    assert context['routes'] == expected
    assert inventory(tmp_path) == before
    assert len(context['folders']) == 3
    assert '课程设计报告' not in context['prompt_context']
    assert f'{count + 1}次复制' in context['prompt_context']

    def controlled_planner(task_id, goal, workspace):
        raw = [dict(tool='list_files', description='扫描', arguments={'workspace': workspace, 'recursive': False}),
               dict(tool='read_document', description='读规则', arguments={'path': str(tmp_path / '提交规则.txt')})]
        raw += [dict(tool='create_folder', description='建目录', arguments={'path': str(tmp_path / folder)})
                for folder in context['folders']]
        raw += [dict(tool='copy_file', description='复制', arguments={
            'source': str(tmp_path / name), 'destination': str(tmp_path / relative)})
            for name, relative in expected.items()]
        # Exercise actual Planner prompt/validation, with a controlled model reply.
        def generate(prompt):
            assert context['prompt_context'] in prompt
            return json.dumps({'steps': raw})
        return plan_task(task_id, goal, workspace, generate=generate)

    service = TaskService(planner=controlled_planner)
    task = service.create('按实际要求归档\n' + context['prompt_context'], str(tmp_path))
    tid = task['task_id']
    service.run(tid)
    snapshot = service.snapshot(tid)
    assert snapshot['task']['status'] == 'awaiting_approval', snapshot
    assert not (tmp_path / '整理归档').exists()
    with pytest.raises(TaskConflict):
        service.decide(tid, 'wrong-preview', approve=True)
    completed = service.decide(tid, snapshot['preview_id'], approve=True)
    assert completed['task']['status'] == 'completed', completed
    record = {'baseline': before, 'routes': context['routes']}
    verified = audit(service, tid, {str(tmp_path): record})
    assert verified['status'] == 'controlled_pass', verified['checks']
    assert len(verified['copies']) == count + 1
    assert inventory(tmp_path) == before
    for name, relative in expected.items():
        assert (tmp_path / name).read_bytes() == (tmp_path / relative).read_bytes()
    with pytest.raises(TaskConflict):
        service.decide(tid, snapshot['preview_id'], approve=True)
    # Copies cannot be reported as correct after destination tampering.
    (tmp_path / next(iter(expected.values()))).write_bytes(b'changed')
    assert audit(service, tid, {str(tmp_path): record})['status'] == 'failed'


def test_no_mapping_no_invented_final_version(tmp_path):
    (tmp_path / 'release_v1.txt').write_text('Approved version. Actual task decides use.')
    (tmp_path / 'release_v8.txt').write_text('Experimental draft, not approved.')
    result = organization_input(tmp_path)
    assert result['routes'] == {}
    assert result['folders'] == []
    assert len(result['tool_inputs']) == 3
    assert 'Approved version' in result['prompt_context']
    assert 'v3' not in result['prompt_context']
    assert '7个create_folder' not in result['prompt_context']
    assert set(p.name for p in tmp_path.iterdir()) == {'release_v1.txt', 'release_v8.txt'}


def test_renamed_requirement_and_changed_final_selection(tmp_path):
    names = ['arbitrary.txt', 'report_v1.docx', 'report_v9.docx']
    from docx import Document
    for name in names[1:]:
        doc = Document(); doc.add_paragraph('report content'); doc.save(tmp_path / name)
    routes = {names[0]: 'result/rules/' + names[0], names[1]: 'result/final/' + names[1],
              names[2]: 'result/archive/' + names[2]}
    (tmp_path / names[0]).write_text('\n'.join('[整理规则] ' + n + ' => ' + p
        for n, p in routes.items()))
    assert organization_input(tmp_path)['routes'] == routes


@pytest.mark.parametrize('destination', ['../cat/a.txt', '/out/cat/a.txt', 'out/../a.txt',
    'out//a.txt', 'out/cat/b.txt', 'C:/cat/a.txt', 'out/CON/a.txt', 'out/cat./a.txt',
    'out/cat:stream/a.txt', 'out/cat/a.txt/extra'])
def test_illegal_paths_rejected(destination):
    with pytest.raises(ValueError):
        parse_routes('[整理规则] a.txt => ' + destination, ['a.txt'])


def test_missing_extra_duplicate_and_cross_platform_collisions():
    line = '[整理规则] a.txt => out/cat/a.txt'
    for text, names in [(line, ['a.txt', 'b.txt']), (line, []), (line + '\n' + line, ['a.txt']),
                        (line, ['a.txt', 'A.txt'])]:
        with pytest.raises(ValueError):
            parse_routes(text, names)
    with pytest.raises(ValueError):
        parse_routes(line + '\n[整理规则] b.txt => out/Cat/b.txt', ['a.txt', 'b.txt'])


def test_existing_output_and_unreadable_inputs(tmp_path):
    fixture(tmp_path, 1)
    (tmp_path / '整理归档').mkdir()
    with pytest.raises(ValueError, match='已存在'):
        organization_input(tmp_path)
    (tmp_path / '整理归档').rmdir()
    (tmp_path / '新要求.pdf').write_bytes(b'not a pdf')
    with pytest.raises(ValueError, match='无法读取'):
        organization_input(tmp_path)


def test_read_limit_is_not_silently_truncated(tmp_path):
    for i in range(11):
        (tmp_path / f'item_{i}.txt').write_text('content')
    with pytest.raises(ValueError, match='超过10'):
        organization_input(tmp_path)


def test_links_rejected_before_read(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text('source')
    try:
        (tmp_path / 'link.txt').symlink_to(source)
    except OSError:
        pytest.skip('Symlinks not available on this host')
    # Scanner may omit symlinks; it must never return their text as independent inputs.
    try:
        result = organization_input(tmp_path)
    except ValueError:
        return
    assert all(r.get('data', {}).get('document', {}).get('filename') != 'link.txt'
               for r in result['tool_inputs'])
