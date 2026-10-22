const test = require('node:test');
const assert = require('node:assert/strict');
const Flow = require('../agent-flow-visualization.js');

function stage(html, key) {
  const match = html.match(new RegExp('<article class="agent-flow-stage"[^>]*data-stage="' + key + '"[^>]*>'));
  assert.ok(match, 'missing stage ' + key);
  return match[0];
}

test('renders a connected nine-stage graph before a task starts', () => {
  const html = Flow.render(null, 'real');
  assert.match(html, /课程材料整理流程/);
  assert.match(html, /agent-flow-graph/);
  assert.equal((html.match(/class="agent-flow-stage"/g) || []).length, 9);
  assert.match(stage(html, 'scan'), /data-path="right"/);
  assert.match(stage(html, 'read'), /data-path="down"/);
  assert.match(stage(html, 'versions'), /data-path="left"/);
  assert.match(stage(html, 'result'), /data-path="none"/);
  assert.match(html, /等待任务/);
});

test('maps real plan steps onto graph stages and preserves their returned statuses', () => {
  const snapshot = {
    task: {task_id:'t1', status:'executing'},
    plan: {steps:[
      {description:'List all files in the workspace to discover documents.', tool:'list_files', status:'completed', risk:'low'},
      {description:'Read the report document.', tool:'read_document', status:'running', risk:'medium'},
      {description:'Compare report versions.', tool:'compare_versions', status:'pending', risk:'medium'},
      {description:'Copy the selected files.', tool:'copy_file', status:'pending', risk:'medium'}
    ]}
  };
  const html = Flow.render(snapshot, 'real');
  assert.match(stage(html, 'scan'), /data-status="completed"/);
  assert.match(stage(html, 'read'), /data-status="running"/);
  assert.match(stage(html, 'versions'), /data-status="pending"/);
  assert.match(stage(html, 'execute'), /data-status="pending"/);
  assert.match(html, /Real Mode · 实时任务状态/);
  assert.match(html, /agent-flow-arrow/);
});

test('does not imply that unreturned stages completed just because the task is complete', () => {
  const snapshot = {
    task: {task_id:'t2', status:'completed'},
    plan: {steps:[{description:'List all files in the workspace to discover documents.', tool:'list_files', status:'completed', risk:'low'}]}
  };
  const html = Flow.render(snapshot, 'real');
  assert.match(stage(html, 'scan'), /data-status="completed"/);
  assert.match(stage(html, 'plan'), /data-status="completed"/);
  assert.match(stage(html, 'versions'), /data-status="not-returned"/);
  assert.match(stage(html, 'execute'), /data-status="not-returned"/);
  assert.match(html, /未返回的阶段不会被标记为已完成/);
});

test('shows the approval stage as waiting when the current task awaits approval', () => {
  const html = Flow.render({
    task:{task_id:'t3',status:'awaiting_approval'},
    plan:{steps:[{description:'Copy selected files after approval.',tool:'copy_file',status:'awaiting_approval',risk:'medium'}]}
  }, 'real');
  assert.match(stage(html, 'approve'), /data-status="awaiting_approval"/);
  assert.match(stage(html, 'execute'), /data-status="awaiting_approval"/);
});

test('mock mode is explicitly labeled as simulated', () => {
  const html = Flow.render({task:{status:'created'},plan:{steps:[]}}, 'mock');
  assert.match(html, /Mock Mode · 模拟任务数据/);
});

test('escapes untrusted plan text and tool metadata', () => {
  const html = Flow.render({
    task:{status:'executing'},
    plan:{steps:[{description:'<img src=x onerror=alert(1)>',tool:'read_document <script>x</script>',status:'running',risk:'<b>high</b>'}]}
  }, 'real');
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>x<\/script>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;script&gt;x&lt;\/script&gt;/);
});

test('summary counts only actual step statuses', () => {
  const summary = Flow.summarize([
    {status:'completed'}, {status:'running'}, {status:'failed'}, {status:'awaiting_approval'}, {status:'unexpected'}
  ]);
  assert.deepEqual(
    {total:summary.total,completed:summary.completed,running:summary.running,failed:summary.failed,awaitingApproval:summary.awaitingApproval,unknown:summary.unknown},
    {total:5,completed:1,running:1,failed:1,awaitingApproval:1,unknown:1}
  );
});

test('highlights the current stage based on the live task status and active step', () => {
  const snapshot = {
    task: {task_id:'t-current', status:'executing'},
    plan: {steps:[
      {description:'List all files in the workspace to discover documents.', tool:'list_files', status:'completed', risk:'low'},
      {description:'Read the report document.', tool:'read_document', status:'running', risk:'medium'},
      {description:'Copy selected files.', tool:'copy_file', status:'pending', risk:'medium'}
    ]}
  };
  const html = Flow.render(snapshot, 'real');
  assert.match(stage(html, 'read'), /data-current="true"/);
  assert.match(stage(html, 'scan'), /data-current="false"/);
  assert.match(html, /当前环节/);
});

test('moves focus to planning, approval, verification and result as task status changes', () => {
  const cases = [
    [{task:{status:'planning'},plan:{steps:[]}}, 'plan'],
    [{task:{status:'awaiting_approval'},plan:{steps:[]}}, 'approve'],
    [{task:{status:'verifying'},plan:{steps:[]}}, 'verify'],
    [{task:{status:'completed'},plan:{steps:[]},final_report:{summary:'Verified final result'}}, 'result']
  ];
  cases.forEach(function (item) {
    const html = Flow.render(item[0], 'real');
    assert.match(stage(html, item[1]), /data-current="true"/);
  });
});

test('planner connection failure highlights planning without inventing completed stages', () => {
  const html = Flow.render({
    task:{task_id:'t-failed',status:'failed'},
    error:'Planner model request failed (connection failed)',
    plan:{steps:[]}
  }, 'real');
  assert.match(stage(html, 'plan'), /data-current="true"/);
  assert.match(stage(html, 'plan'), /data-status="failed"/);
  assert.match(stage(html, 'execute'), /data-status="not-returned"/);
});
