(function (root) {
  'use strict';

  const STATUS = {
    pending: {label: '待执行', symbol: '○', className: 'pending'},
    running: {label: '进行中', symbol: '●', className: 'running'},
    completed: {label: '已完成', symbol: '✓', className: 'completed'},
    failed: {label: '失败', symbol: '!', className: 'failed'},
    awaiting_approval: {label: '等待审批', symbol: 'Ⅱ', className: 'awaiting-approval'},
    skipped: {label: '已跳过', symbol: '—', className: 'skipped'}
  };

  const TASK_STATUS = {
    created: '任务已创建',
    planning: '正在规划',
    executing: '执行中',
    verifying: '验证中',
    awaiting_approval: '等待审批',
    completed: '任务已完成',
    failed: '任务失败'
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[character];
    });
  }

  function asArray(value) {
    return Array.isArray(value) ? value.filter(function (item) { return item && typeof item === 'object'; }) : [];
  }

  function normalizeStatus(value) {
    const key = typeof value === 'string' ? value : '';
    return STATUS[key] ? {key: key, ...STATUS[key]} : {
      key: 'unknown',
      label: key ? '未识别状态：' + key : '状态未提供',
      symbol: '·',
      className: 'unknown'
    };
  }

  function summarize(steps) {
    const counts = {total: steps.length, completed: 0, running: 0, failed: 0, awaitingApproval: 0, pending: 0, skipped: 0, unknown: 0};
    steps.forEach(function (step) {
      const key = normalizeStatus(step.status).key;
      if (key === 'completed') counts.completed++;
      else if (key === 'running') counts.running++;
      else if (key === 'failed') counts.failed++;
      else if (key === 'awaiting_approval') counts.awaitingApproval++;
      else if (key === 'pending') counts.pending++;
      else if (key === 'skipped') counts.skipped++;
      else counts.unknown++;
    });
    return counts;
  }

  function taskNote(taskStatus) {
    if (taskStatus === 'awaiting_approval') return 'Agent 已提交待审批方案；审批前的文件操作尚未执行。';
    if (taskStatus === 'completed') return '任务状态已完成；最终结果及文件核验以 Final Result 与执行证据为准。';
    if (taskStatus === 'failed') return '任务失败；请结合错误提示和工具执行记录定位原因。';
    if (taskStatus === 'planning') return 'Agent 正在生成计划；流程图只展示当前快照已返回的步骤。';
    if (taskStatus === 'executing' || taskStatus === 'verifying') return '正在接收任务状态更新；节点状态随 Agent 返回的执行快照刷新。';
    if (taskStatus === 'created') return '任务已创建，等待 Agent 返回计划和步骤状态。';
    return '步骤和状态来自当前 Agent 任务快照，不补造未返回的节点。';
  }

  function render(snapshot, mode) {
    if (!snapshot || !snapshot.task || typeof snapshot.task !== 'object') {
      return '<div class="agent-flow-empty"><span class="agent-flow-empty-icon" aria-hidden="true">⌁</span><strong>等待 Agent 任务</strong><p>填写 Workspace 和目标后点击 Run Agent。这里会把 Agent 返回的计划步骤显示为相连的流程节点。</p></div>';
    }

    const task = snapshot.task;
    const steps = asArray(snapshot.plan && snapshot.plan.steps);
    const counts = summarize(steps);
    const taskStatus = typeof task.status === 'string' ? task.status : '';
    const taskLabel = TASK_STATUS[taskStatus] || (taskStatus ? '任务状态：' + taskStatus : '任务状态未知');
    const modeLabel = mode === 'mock' ? 'Mock 模式 · 模拟任务数据' : 'Real Mode · 当前任务快照';
    const percent = counts.total ? Math.round(counts.completed / counts.total * 100) : 0;
    const summary = [
      '<span><strong>' + counts.total + '</strong> 个计划步骤</span>',
      '<span><strong>' + counts.completed + '</strong> 已完成</span>',
      '<span><strong>' + counts.running + '</strong> 进行中</span>',
      '<span><strong>' + counts.failed + '</strong> 失败</span>'
    ].join('');

    let nodes;
    if (!steps.length) {
      nodes = '<div class="agent-flow-empty compact"><strong>计划步骤尚未返回</strong><p>当前任务状态：' + escapeHtml(taskLabel) + '。不会用预设动画替代 Agent 的实际计划。</p></div>';
    } else {
      nodes = steps.map(function (step, index) {
        const status = normalizeStatus(step.status);
        const description = typeof step.description === 'string' && step.description.trim()
          ? step.description
          : (typeof step.tool === 'string' && step.tool ? step.tool : '未提供步骤说明');
        const tool = typeof step.tool === 'string' && step.tool ? step.tool : '工具名称未提供';
        const risk = typeof step.risk === 'string' && step.risk ? step.risk : '';
        const connector = index === steps.length - 1 ? '' : '<span class="agent-flow-connector" aria-hidden="true"></span>';
        return '<article class="agent-flow-item" data-status="' + escapeHtml(status.className) + '" role="listitem">' +
          '<div class="agent-flow-rail"><span class="agent-flow-marker" aria-label="' + escapeHtml(status.label) + '">' + escapeHtml(status.symbol) + '</span>' + connector + '</div>' +
          '<div class="agent-flow-node"><div class="agent-flow-node-heading"><span class="agent-flow-index">STEP ' + String(index + 1).padStart(2, '0') + '</span><span class="agent-flow-status">' + escapeHtml(status.label) + '</span></div>' +
          '<strong class="agent-flow-description">' + escapeHtml(description) + '</strong>' +
          '<div class="agent-flow-meta"><span class="agent-flow-tool">' + escapeHtml(tool) + '</span>' +
          (risk ? '<span class="agent-flow-risk" data-risk="' + escapeHtml(risk) + '">风险：' + escapeHtml(risk) + '</span>' : '') +
          '</div></div></article>';
      }).join('');
    }

    return '<section class="agent-flow" data-task-status="' + escapeHtml(taskStatus) + '">' +
      '<div class="agent-flow-overview"><div><span class="agent-flow-task-label">当前任务</span><strong>' + escapeHtml(taskLabel) + '</strong></div><span class="agent-flow-mode">' + escapeHtml(modeLabel) + '</span></div>' +
      '<p class="agent-flow-note">' + escapeHtml(taskNote(taskStatus)) + '</p>' +
      '<div class="agent-flow-summary">' + summary + '</div>' +
      '<div class="agent-flow-progress" role="progressbar" aria-label="已完成计划步骤比例" aria-valuemin="0" aria-valuemax="' + counts.total + '" aria-valuenow="' + counts.completed + '"><span style="width:' + percent + '%"></span></div>' +
      '<div class="agent-flow-list" role="list" aria-label="Agent 计划步骤">' + nodes + '</div>' +
      '<p class="agent-flow-footnote">此图根据当前任务返回的 plan.steps 和每步 status 实时渲染；不会自行补充模型调用、文件复制或校验结果。</p>' +
      '</section>';
  }

  const api = {escapeHtml: escapeHtml, normalizeStatus: normalizeStatus, summarize: summarize, render: render};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.AgentFlowVisualization = api;
})(typeof window === 'undefined' ? globalThis : window);