"""Controlled Planner tests, real TaskService/tools/files; no LLM calls."""
from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService, TaskConflict
from fileforge.api.agent import get_service
from fileforge.api.server import app


def service_for(root, *, analysis_first=False):
    (root/'notice.txt').write_text('必须提交课程报告。最终稿需本人确认。',encoding='utf-8')
    calls=[]
    def planner(tid, goal, workspace):
        calls.append(goal)
        assert 'Document read successfully' in goal
        if analysis_first and len(calls)==1:
            return validate_plan({'steps':[{'tool':'extract_requirements','description':'Extract actual requirements','arguments':{}}]},tid,goal)
        if '"answer":' not in goal:
            return validate_plan({'steps':[],'questions':[{'question':'采用哪份报告？','reason':'没有已确认定稿的证据',
                'file_paths':[str(root/'notice.txt')],'options':['保留为历史参考','用于提交']} ]},tid,goal)
        destination=root/('history' if '保留为历史参考' in goal.split('User answers')[1].split('"answer":')[1] else 'submit')
        return validate_plan({'steps':[
            {'tool':'create_folder','description':'Create approved target','arguments':{'path':str(destination)}},
            {'tool':'copy_file','description':'Copy approved source','arguments':{'source':str(root/'notice.txt'),'destination':str(destination/'notice.txt')}}]},tid,goal)
    return TaskService(planner=planner),calls


def paused(root, analysis_first=False):
    service,calls=service_for(root,analysis_first=analysis_first)
    task=service.create('整理并在证据不足时询问',str(root),interactive=True)
    service.run(task['task_id']);s=service.snapshot(task['task_id'])
    assert s['task']['status']=='awaiting_clarification',s.get('error')
    return service,calls,s


def answers(s,text='保留为历史参考'):
    return [{'question_id':q['question_id'],'answer':text} for q in s['clarification']['questions']]


def test_read_dependency_is_real_and_precedes_extraction(tmp_path):
    service,calls,s=paused(tmp_path,True)
    assert [r['tool'] for r in s['results']]==['list_files','read_document','extract_requirements']
    assert all(r['success'] for r in s['results'])
    assert len(calls)==2
    assert s['preview_id'] is None and not s['pending_operations']


@pytest.mark.parametrize('choice,folder',[('保留为历史参考','history'),('用于提交','submit')])
def test_answer_replans_same_task_and_requires_fresh_approval(tmp_path,choice,folder):
    service,calls,s=paused(tmp_path);tid=s['task']['task_id'];token=s['clarification']['clarification_id']
    with pytest.raises(TaskConflict):service.decide(tid,'invented',approve=True)
    service.answer(tid,token,answers(s,choice))
    with pytest.raises(TaskConflict):service.answer(tid,token,answers(s,choice))
    service.run(tid);preview=service.snapshot(tid)
    assert preview['task']['task_id']==tid and preview['task']['status']=='awaiting_approval'
    assert not (tmp_path/folder).exists()
    assert len(calls)==2 and preview['clarification'] is None
    service.decide(tid,preview['preview_id'],approve=True)
    final=service.snapshot(tid)
    assert final['task']['status']=='completed'
    assert final['results'][-1]['data']['passed']
    assert (tmp_path/folder/'notice.txt').read_bytes()==(tmp_path/'notice.txt').read_bytes()
    with pytest.raises(TaskConflict):service.decide(tid,preview['preview_id'],approve=True)


@pytest.mark.parametrize('kind',['empty','duplicate','unknown','blank'])
def test_invalid_answers_do_not_consume_current_question(tmp_path,kind):
    service,_,s=paused(tmp_path);a=answers(s)
    if kind=='empty':a=[]
    if kind=='duplicate':a=a+a
    if kind=='unknown':a[0]['question_id']='wrong'
    if kind=='blank':a[0]['answer']=' '
    with pytest.raises(ValueError):service.answer(s['task']['task_id'],s['clarification']['clarification_id'],a)
    assert service.snapshot(s['task']['task_id'])['clarification']==s['clarification']


@pytest.mark.parametrize('stage',['answers','approval'])
def test_same_length_change_restored_mtime_blocks_continuation(tmp_path,stage):
    import os
    service,_,s=paused(tmp_path);tid=s['task']['task_id']
    if stage=='approval':
        service.answer(tid,s['clarification']['clarification_id'],answers(s));service.run(tid);s=service.snapshot(tid)
    p=tmp_path/'notice.txt';stat=p.stat();raw=p.read_bytes();p.write_bytes(b'X'*len(raw));os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    with pytest.raises(TaskConflict):
        if stage=='answers':service.answer(tid,s['clarification']['clarification_id'],answers(s))
        else:service.decide(tid,s['preview_id'],approve=True)
    assert not (tmp_path/'history').exists()


def test_cross_task_answer_rejected(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    service,_,one=paused(a)
    other=service.create('second',str(b),interactive=True)
    with pytest.raises(TaskConflict):service.answer(other['task_id'],one['clarification']['clarification_id'],answers(one))


def test_source_outside_question_rejected(tmp_path):
    service=TaskService(planner=lambda tid,g,w:validate_plan({'steps':[],'questions':[{'question':'What?','reason':'unknown','file_paths':[str(tmp_path.parent/'outside.txt')],'options':[]}]},tid,g))
    tid=service.create('ask',str(tmp_path),interactive=True)['task_id'];service.run(tid)
    assert service.snapshot(tid)['task']['status']=='failed'
    assert service.snapshot(tid)['preview_id'] is None


def test_http_answer_endpoint_and_stale_token(tmp_path):
    service,_,s=paused(tmp_path);tid=s['task']['task_id']
    app.dependency_overrides[get_service]=lambda:service
    try:
        with TestClient(app) as client:
            url=f'/api/agent/tasks/{tid}/answers';body={'clarification_id':s['clarification']['clarification_id'],'answers':answers(s)}
            assert client.post(url,json={}).status_code==400
            assert client.post(url,json=body).status_code==202
            for _ in range(100):
                if service.snapshot(tid)['task']['status']!='planning':break
                time.sleep(.01)
            assert service.snapshot(tid)['task']['status']=='awaiting_approval'
            assert client.post(url,json=body).status_code==409
            assert client.get(f'/api/agent/tasks/{tid}/report').status_code==409
            assert client.post('/api/agent/tasks/absent/answers',json=body).status_code==404
    finally:app.dependency_overrides.clear()


def test_private_selectors_expand_exact_real_documents_without_public_field_change(tmp_path):
    import json
    from fileforge.document import read_document
    from fileforge.agent.planner import plan_task
    p=tmp_path/'notice.txt';p.write_text('必须提交报告。',encoding='utf-8');read=read_document(str(p))
    payload={'steps':[{'tool':'extract_requirements','description':'Read actual notice requirements',
                      'arguments':{'document_paths':[str(p)]}}],'questions':[]}
    plan=plan_task('task','Analyze',str(tmp_path),generate=lambda _:json.dumps(payload),
                   interactive_context={'results':[read],'answers':[]})
    assert plan['steps'][0]['arguments']=={'documents':[read['data']['document']]}
    assert 'document_paths' not in plan['steps'][0]['arguments']


@pytest.mark.parametrize('selector',['unread','duplicate','write'])
def test_private_selectors_cannot_invent_documents_or_supply_write_arguments(tmp_path,selector):
    import json
    from fileforge.document import read_document
    from fileforge.agent.planner import plan_task
    p=tmp_path/'n.txt';p.write_text('notice',encoding='utf-8');read=read_document(str(p))
    paths=[str(p)] if selector=='write' else [str(p),str(p)] if selector=='duplicate' else [str(tmp_path/'unknown.txt')]
    payload={'steps':[{'tool':'copy_file' if selector=='write' else 'extract_requirements','description':'invalid selector','arguments':{'document_paths':paths}}]}
    with pytest.raises(ValueError):plan_task('task','Analyze',str(tmp_path),generate=lambda _:json.dumps(payload),interactive_context={'results':[read],'answers':[]})


def test_default_planner_feedback_blocks_unsupported_reads_then_analyzes_before_questions(tmp_path,monkeypatch):
    import json
    import fileforge.agent.planner as planner_module
    p=tmp_path/'notice.txt';p.write_text('必须提交报告。',encoding='utf-8');unsupported=tmp_path/'code.cpp';unsupported.write_text('synthetic code')
    calls=[]
    question={'question':'确认用途？','reason':'证据不足','file_paths':[str(unsupported)],'options':['保留原处']}
    drafts=[{'steps':[{'tool':'read_document','description':'invalid draft','arguments':{'path':str(unsupported)}}]},
            {'steps':[{'tool':'extract_requirements','description':'actual notice analysis','arguments':{'document_paths':[str(p)]}}],'questions':[question]},
            {'steps':[],'questions':[question]}]
    def generate(prompt,**kwargs):calls.append(prompt);return json.dumps(drafts[len(calls)-1])
    monkeypatch.setattr(planner_module,'_generate_local',generate)
    service=TaskService();tid=service.create('Analyze uncertain files',str(tmp_path),interactive=True)['task_id'];service.run(tid);s=service.snapshot(tid)
    assert s['task']['status']=='awaiting_clarification',s['error']
    assert [r['tool'] for r in s['results']]==['list_files','read_document','extract_requirements']
    assert all(r['success'] for r in s['results']) and len(calls)==3
    assert 'Unsupported read_document formats' in calls[1]


def test_interactive_read_limit_is_not_bypassed(tmp_path):
    for i in range(11):(tmp_path/f'{i}.txt').write_text('fixture')
    service=TaskService(planner=lambda *args:pytest.fail('Must not invoke Planner beyond read limit'))
    tid=service.create('Analyze',str(tmp_path),interactive=True)['task_id'];service.run(tid);s=service.snapshot(tid)
    assert s['task']['status']=='failed' and 'limit' in s['error']
    assert [r['tool'] for r in s['results']]==['list_files']
