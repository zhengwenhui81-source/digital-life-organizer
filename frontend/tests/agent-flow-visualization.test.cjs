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
  assert.match(html, /Real Mode · 当前任务快照/);
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
  assert.match(html, /不代表该操作已执行/);
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