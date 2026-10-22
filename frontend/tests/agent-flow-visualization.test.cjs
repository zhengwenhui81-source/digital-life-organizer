const test = require('node:test');
const assert = require('node:assert/strict');
const Flow = require('../agent-flow-visualization.js');

test('empty state does not invent a plan when no task snapshot exists', () => {
  const html = Flow.render(null, 'real');
  assert.match(html, /等待 Agent 任务/);
  assert.doesNotMatch(html, /扫描工作空间/);
});

test('renders actual plan steps in order with their returned statuses', () => {
  const snapshot = {
    task: {task_id:'t1', status:'executing'},
    plan: {steps:[
      {description:'扫描工作空间', tool:'scan_workspace', status:'completed', risk:'low'},
      {description:'读取报告', tool:'read_document', status:'running', risk:'medium'},
      {description:'生成目录计划', tool:'plan_directories', status:'pending', risk:'low'}
    ]}
  };
  const html = Flow.render(snapshot, 'real');
  assert.ok(html.indexOf('扫描工作空间') < html.indexOf('读取报告'));
  assert.ok(html.indexOf('读取报告') < html.indexOf('生成目录计划'));
  assert.match(html, /data-status="completed"/);
  assert.match(html, /data-status="running"/);
  assert.match(html, /data-status="pending"/);
  assert.match(html, /Real Mode/);
});

test('mock mode is explicitly labeled as simulated', () => {
  const html = Flow.render({task:{status:'created'}, plan:{steps:[]}}, 'mock');
  assert.match(html, /Mock 模式 · 模拟任务数据/);
});

test('escapes untrusted plan text and risk metadata', () => {
  const html = Flow.render({
    task:{status:'executing'},
    plan:{steps:[{description:'<img src=x onerror=alert(1)>',tool:'<script>x</script>',status:'running',risk:'<b>high</b>'}]}
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
  assert.deepEqual({total:summary.total,completed:summary.completed,running:summary.running,failed:summary.failed,awaitingApproval:summary.awaitingApproval,unknown:summary.unknown},
    {total:5,completed:1,running:1,failed:1,awaitingApproval:1,unknown:1});
});