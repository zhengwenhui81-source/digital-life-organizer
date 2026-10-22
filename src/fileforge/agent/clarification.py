"""Opt-in evidence-first clarification using the existing executor and write gate."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets

from fileforge.agent.executor import create_execution, execute
from fileforge.agent.planner import validate_plan, plan_task, PLANNER_TRACE


def sources(root):
    """Bind decisions to actual source bytes; never follow reparse points."""
    result = {}
    for p in Path(root).rglob('*'):
        stat = p.lstat()
        if p.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Interactive workspace contains a link/reparse point')
        if p.is_file():
            result[str(p.resolve())] = (stat.st_size, stat.st_mtime_ns,
                                       hashlib.sha256(p.read_bytes()).hexdigest())
    return result


def append_plan(service, entry, plan):
    """Append genuinely pending steps without erasing any prior ToolResults."""
    root = Path(entry['task']['workspace'])
    service._check_plan_paths(plan, root)
    state = entry['execution']
    if state is None:
        entry['execution'] = create_execution(plan)
        return
    steps = state['plan']['steps']
    for step in plan['steps']:
        step = deepcopy(step)
        step['step_id'] = 'step_%03d' % (len(steps) + 1)
        steps.append(step)
    state['status'] = 'executing'


def run(service, entry):
    root = Path(entry['task']['workspace'])
    tid = entry['task']['task_id']
    try:
        if entry['execution'] is None:
            # Real discovery is recorded in this Task, not copied from the goal.
            scan = validate_plan({'steps': [{'tool': 'list_files', 'description': 'Discover workspace',
                                            'arguments': {'workspace': str(root), 'recursive': False}}]}, tid, entry['task']['user_goal'])
            append_plan(service, entry, scan)
            state = entry['execution']
            execute(state, service._router, resolver=service._scoped_resolver(root, state['plan']['steps']))
            if state['status'] != 'completed':
                service._finish(entry)
                return
            files = state['results'][0]['data']['files']
            readable = [f for f in files if Path(f['path']).suffix.lower() in {'.txt', '.pdf', '.docx', '.xlsx'}]
            if len(readable) > 10:
                raise ValueError('Interactive readable document limit is 10; no partial coverage claimed')
            if readable:
                reads = validate_plan({'steps': [{'tool': 'read_document', 'description': 'Read actual document',
                                                  'arguments': {'path': f['path']}} for f in readable]}, tid, entry['task']['user_goal'])
                append_plan(service, entry, reads)
                execute(state, service._router, resolver=service._scoped_resolver(root, state['plan']['steps']))
                if state['status'] != 'completed':
                    service._finish(entry)
                    return
            entry['source_evidence'] = sources(root)
        state = entry['execution']
        feedback = []
        for _ in range(4):
            if sources(root) != entry['source_evidence']:
                raise ValueError('Sources changed before interactive planning')
            instruction = (
                '\nINTERACTIVE MODE: Real Task results follow; these are authoritative executed evidence. '
                'Return JSON {"steps": [...], "questions": [...]} using existing tools. '
                'Questions each contain exactly question, reason, file_paths (absolute existing files), options (strings). '
                'If evidence is insufficient, ask specific file questions with reasons and choices; do not assign final roles. '
                'Questions may use steps:[]; never invent an ask-user tool. Do not repeat already successful reads/analysis. '
                'If analysis is still needed, return only applicable low-risk analysis steps; you will receive actual results next. '
                'Use only the relevant real Document objects for extract_requirements and compare_versions; '
                'a latest candidate is not user adoption. Only after uncertainty is resolved propose copy/create steps. '
                'Do not move/delete/overwrite, or plan verify_result (TaskService verifies approved writes automatically). '
                'Do not claim unsupported file bodies were read. Do not use fixed demo assumptions. '
                '\nActual results: ' + json.dumps(state['results'], ensure_ascii=False) +
                '\nUser answers (not permission to write): ' + json.dumps(entry['answer_history'], ensure_ascii=False))
            if service._planner is plan_task:
                events = []
                token = PLANNER_TRACE.set(events)
                try:
                    plan = plan_task(tid, entry['task']['user_goal'], str(root),
                                     interactive_context={'results':state['results'], 'answers':entry['answer_history'],
                                                          'planning_feedback':feedback})
                except ValueError as exc:
                    # Bounded structural repair, never a fabricated ToolResult or HTTP retry.
                    feedback.append({'rejected_draft':str(exc), 'instruction':'Use only actual read document paths and valid nonempty steps or questions. Do not repeat resolved questions.'})
                    continue
                finally:
                    PLANNER_TRACE.reset(token)
                    with service._lock:
                        entry.setdefault('planner_events', []).extend(deepcopy(events))
            else:
                plan = service._planner(tid, entry['task']['user_goal'] + instruction, str(root))
            plan = validate_plan(plan, tid, entry['task']['user_goal'])
            unsupported_reads = [s['arguments'].get('path') for s in plan['steps']
                                 if s['tool']=='read_document' and s['arguments'].get('path') and
                                 Path(s['arguments']['path']).suffix.lower() not in {'.txt','.pdf','.docx','.xlsx'}]
            if unsupported_reads:
                feedback.append({'rejected_draft':'Unsupported read_document formats',
                                 'paths':unsupported_reads,
                                 'instruction':'Do not read these formats or claim their bodies were read. Use only the existing real supported Document results for analysis; leave unknown uses uncertain.'})
                continue
            if plan.get('questions') and any(s['risk']=='low' for s in plan['steps']):
                analysis = {**plan, 'steps':[s for s in plan['steps'] if s['risk']=='low']}
                analysis.pop('questions',None)
                append_plan(service,entry,analysis)
                execute(state,service._router,resolver=service._scoped_resolver(root,state['plan']['steps']))
                if state['status']=='failed':
                    service._finish(entry)
                    return
                # Re-ask the Planner with actual analysis results, not its predicted results.
                continue
            if plan.get('questions'):
                questions = deepcopy(plan['questions'])
                for q in questions:
                    for raw in q['file_paths']:
                        path = Path(raw).resolve()
                        if str(path) not in entry['source_evidence']:
                            raise ValueError('Clarification references an unobserved/outside source')
                    q['question_id'] = 'question_' + secrets.token_hex(12)
                # Discard proposed writes rather than executing alongside questions.
                entry['clarification'] = {'clarification_id': 'clarification_' + secrets.token_hex(24), 'questions': questions}
                entry['preview_id'] = None
                state['pending_operations'] = []
                state['status'] = entry['task']['status'] = 'awaiting_clarification'
                return
            if not plan['steps']:
                raise ValueError('Planner produced neither questions nor operations')
            if any(s['tool'] in {'move_file', 'build_package', 'verify_result'} for s in plan['steps']):
                raise ValueError('Interactive mode supports approved create/copy only')
            append_plan(service, entry, plan)
            execute(state, service._router, resolver=service._scoped_resolver(root, state['plan']['steps']))
            if state['status'] == 'awaiting_approval':
                service._finish(entry)
                return
            if state['status'] == 'failed':
                service._finish(entry)
                return
        raise ValueError('Interactive planning round limit reached; no automatic retry')
    except Exception as exc:
        with service._lock:
            entry['task']['status'] = 'failed'
            entry['error'] = str(exc)
            entry['preview_id'] = None
            entry['clarification'] = None
            if entry['execution']:
                entry['execution']['status'] = 'failed'
                entry['execution']['pending_operations'] = []


def accept_answers(service, entry, clarification_id, answers):
    """Called under TaskService lock; consume before scheduling any continuation."""
    from fileforge.agent.service import TaskConflict
    current = entry['clarification']
    if entry['task']['status'] != 'awaiting_clarification' or not current or current['clarification_id'] != clarification_id:
        raise TaskConflict('Clarification is stale or belongs to another task')
    expected = {q['question_id'] for q in current['questions']}
    if (type(answers) is not list or len(answers) != len(expected) or
        any(type(a) is not dict or set(a) != {'question_id', 'answer'} or
            type(a['question_id']) is not str or type(a['answer']) is not str or
            not a['answer'].strip() or len(a['answer']) > 4000 for a in answers) or
        {a['question_id'] for a in answers} != expected):
        raise ValueError('Every current question requires exactly one nonempty answer')
    if sources(entry['task']['workspace']) != entry['source_evidence']:
        raise TaskConflict('Sources changed; answers cannot resume this plan')
    entry['answer_history'].append({'clarification': deepcopy(current), 'answers': deepcopy(answers)})
    entry['clarification'] = None
    entry['preview_id'] = None
    entry['report'] = None
    entry['execution']['pending_operations'] = []
    entry['execution']['status'] = 'executing'
    entry['task']['status'] = 'planning'
