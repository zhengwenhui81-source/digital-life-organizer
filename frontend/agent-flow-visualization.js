(function (root) {
  'use strict';

  const STAGES = [
    {key:'scan', title:'扫描工作空间', subtitle:'建立文件清单与基础元数据', col:1,row:1,path:'right', match:/list_files|scan_workspace|scan_files|list all files|扫描文件/i},
    {key:'identify', title:'识别关键材料', subtitle:'定位课程要求、报告、代码与实验数据', col:2,row:1,path:'right', match:/search_files|extract_requirements|match_requirements|classif|identify|search|识别材料/i},
    {key:'read', title:'读取文档内容', subtitle:'提取可读取的正文与表格', col:3,row:1,path:'right', match:/read_document|extract_text|document_reader|读取文档/i},
    {key:'versions', title:'比较报告版本', subtitle:'分析候选版本与内容差异', col:4,row:1,path:'down', match:/compare_versions|detect_conflicts|version|比较版本|版本分析/i},
    {key:'approve', title:'确认整理方案', subtitle:'关键操作在执行前等待审批', col:4,row:2,path:'left', match:/approval|approve|preview_plan|确认方案/i},
    {key:'execute', title:'创建目录并复制', subtitle:'按已确认方案执行文件操作', col:3,row:2,path:'left', match:/create_directory|copy_file|move_file|execute_operation|apply_operation|write_package_report|创建目录|复制文件/i},
    {key:'verify', title:'校验整理结果', subtitle:'检查目标文件与内容完整性', col:2,row:2,path:'left', match:/verify|checksum|sha.?256|hash|validation|校验|核验/i},
    {key:'result', title:'汇总整理结果', subtitle:'呈现执行记录与最终结果', col:1,row:2,path:'none', match:/final_report|summarize_results|result_report|汇总结果/i}
  ];

  const STATUS = {
    pending: {label:'待执行', symbol:'○', className:'pending'},
    running: {label:'进行中', symbol:'●', className:'running'},
    completed: {label:'已完成', symbol:'✓', className:'completed'},
    failed: {label:'失败', symbol:'!', className:'failed'},
    awaiting_approval: {label:'等待审批', symbol:'Ⅱ', className:'awaiting-approval'},
    skipped: {label:'已跳过', symbol:'—', className:'skipped'}
  };

  const TASK_STATUS = {
    created:'任务已创建', planning:'正在规划', executing:'执行中',
    verifying:'验证中', awaiting_approval:'等待审批',
    completed:'任务已完成', failed:'任务失败'
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[character];
    });
  }

  function asArray(value) {
    return Array.isArray(value) ? value.filter(function (item) { return item && typeof item === 'object'; }) : [];
  }

  function normalizeStatus(value) {
    const key = typeof value === 'string' ? value : '';
    return STATUS[key] ? {key:key, ...STATUS[key]} : {
      key:'unknown', label:key ? '未识别状态：' + key : '状态未提供',
      symbol:'·', className:'unknown'
    };
  }

  function summarize(steps) {
    const counts = {total:steps.length,completed:0,running:0,failed:0,awaitingApproval:0,pending:0,skipped:0,unknown:0};
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

  function stageStatus(stage, snapshot, steps) {
    const taskStatus = snapshot && snapshot.task ? snapshot.task.status : '';
    const matches = steps.filter(function (step) {
      const searchable = [step.tool, step.description, step.name].filter(Boolean).join(' ');
      return stage.match.test(searchable);
    });

    if (matches.length) {
      const keys = matches.map(function (step) { return normalizeStatus(step.status).key; });
      let key = 'pending';
      if (keys.includes('failed')) key = 'failed';
      else if (keys.includes('running')) key = 'running';
      else if (keys.includes('awaiting_approval')) key = 'awaiting_approval';
      else if (keys.every(function (item) { return item === 'completed' || item === 'skipped'; })) {
        key = keys.every(function (item) { return item === 'skipped'; }) ? 'skipped' : 'completed';
      } else if (keys.includes('unknown')) key = 'unknown';
      return {key:key, label:normalizeStatus(key).label, evidence:matches};
    }

    if (stage.key === 'scan' && snapshot && taskStatus === 'created') {
      return {key:'running', label:'任务已创建', evidence:[]};
    }
    if (stage.key === 'result' && snapshot && snapshot.final_report) {
      return {key:'completed', label:'结果已生成', evidence:[]};
    }
    if (stage.key === 'approve' && taskStatus === 'awaiting_approval') {
      return {key:'awaiting_approval', label:'等待审批', evidence:[]};
    }
    if (stage.key === 'plan' && snapshot && snapshot.plan && asArray(snapshot.plan.steps).length) {
      return {key:taskStatus === 'planning' ? 'running' : 'completed', label:taskStatus === 'planning' ? '正在生成' : '计划已生成', evidence:[]};
    }
    if (stage.key === 'plan' && snapshot && taskStatus === 'failed' && /planner|plan|model request/i.test(String(snapshot.error || ''))) {
      return {key:'failed', label:'规划失败', evidence:[]};
    }
    return {key:snapshot ? 'not-returned' : 'idle', label:snapshot ? '当前快照未返回' : '等待任务', evidence:[]};
  }

  function stageMarkup(stage, index, status, snapshot) {
    const evidence = status.evidence || [];
    const actual = evidence.length
      ? '<div class="agent-flow-evidence">' + evidence.slice(0,2).map(function (step) {
          const description = step.description || step.tool || '步骤说明未提供';
          const tool = step.tool ? ' · ' + step.tool : '';
          return '<p title="' + escapeHtml(description) + '">' + escapeHtml(description) + '<small>' + escapeHtml(tool) + '</small></p>';
        }).join('') + (evidence.length > 2 ? '<small>另有 ' + (evidence.length - 2) + ' 个关联步骤</small>' : '') + '</div>'
      : '<div class="agent-flow-stage-hint">' + (snapshot ? '此阶段没有匹配到当前任务的执行步骤' : '开始任务后显示状态') + '</div>';
    const meta = evidence.length ? '<span class="agent-flow-tool-count">' + evidence.length + ' 个关联步骤</span>' : '';
    return '<article class="agent-flow-stage" role="listitem" data-stage="' + stage.key + '" data-status="' + status.key + '" data-path="' + stage.path + '" style="--flow-col:' + stage.col + ';--flow-row:' + stage.row + ';">' +
      '<div class="agent-flow-stage-top"><span class="agent-flow-stage-number">' + String(index + 1).padStart(2,'0') + '</span>' +
      '<span class="agent-flow-stage-state"><i aria-hidden="true">' + (STATUS[status.key] ? STATUS[status.key].symbol : '·') + '</i>' + escapeHtml(status.label) + '</span></div>' +
      '<div class="agent-flow-stage-icon" aria-hidden="true">' + ({scan:'▤',identify:'⌕',read:'▧',versions:'⇄',approve:'◇',execute:'▣',verify:'✓',result:'▤'}[stage.key] || '○') + '</div>' +
      '<strong class="agent-flow-stage-title">' + escapeHtml(stage.title) + '</strong>' +
      '<p class="agent-flow-stage-subtitle">' + escapeHtml(stage.subtitle) + '</p>' +
      actual + meta + '<span class="agent-flow-arrow" aria-hidden="true"></span></article>';
  }

  function render(snapshot, mode) {
    const hasTask = Boolean(snapshot && snapshot.task && typeof snapshot.task === 'object');
    const task = hasTask ? snapshot.task : {};
    const steps = asArray(snapshot && snapshot.plan && snapshot.plan.steps);
    const taskStatus = typeof task.status === 'string' ? task.status : '';
    const taskLabel = TASK_STATUS[taskStatus] || (taskStatus ? '任务状态：' + taskStatus : '等待 Agent 任务');
    const stageStates = STAGES.map(function (stage) {
      return {stage:stage, state:stageStatus(stage, hasTask ? snapshot : null, steps)};
    });
    const counts = {completed:0,running:0,failed:0,awaiting:0,notReturned:0};
    stageStates.forEach(function (item) {
      const key = item.state.key;
      if (key === 'completed') counts.completed++;
      else if (key === 'running') counts.running++;
      else if (key === 'failed') counts.failed++;
      else if (key === 'awaiting_approval') counts.awaiting++;
      else if (key === 'not-returned') counts.notReturned++;
    });
    const modeLabel = mode === 'mock' ? 'Mock Mode · 模拟任务数据' : 'Real Mode · 当前任务快照';
    const percent = Math.round(counts.completed / STAGES.length * 100);
    const note = !hasTask
      ? '点击 Run Agent 后，流程图将跟随任务快照更新；灰色节点表示尚未开始或没有任务证据。'
      : '节点状态根据当前任务快照与计划步骤匹配。灰色节点表示当前任务未返回对应步骤，不代表该操作已执行。';
    const nodes = stageStates.map(function (item, index) {
      return stageMarkup(item.stage, index, item.state, hasTask ? snapshot : null);
    }).join('');

    return '<section class="agent-flow" data-task-status="' + escapeHtml(taskStatus || 'idle') + '">' +
      '<div class="agent-flow-overview"><div><span class="agent-flow-task-label">课程材料整理流程</span><strong>' + escapeHtml(taskLabel) + '</strong></div><span class="agent-flow-mode">' + escapeHtml(modeLabel) + '</span></div>' +
      '<p class="agent-flow-note">' + escapeHtml(note) + '</p>' +
      '<div class="agent-flow-summary">' +
        '<span><strong>' + STAGES.length + '</strong> 个流程阶段</span>' +
        '<span><strong>' + counts.completed + '</strong> 已有完成证据</span>' +
        '<span><strong>' + counts.running + '</strong> 进行中</span>' +
        '<span><strong>' + counts.failed + '</strong> 失败</span>' +
        '<span><strong>' + counts.notReturned + '</strong> 当前快照未返回</span>' +
      '</div>' +
      '<div class="agent-flow-progress" role="progressbar" aria-label="有完成证据的流程阶段比例" aria-valuemin="0" aria-valuemax="' + STAGES.length + '" aria-valuenow="' + counts.completed + '"><span style="width:' + percent + '%"></span></div>' +
      '<div class="agent-flow-graph" role="list" aria-label="课程材料整理流程图">' + nodes + '</div>' +
      '<p class="agent-flow-footnote">连线表示流程阶段的先后关系；节点颜色表示当前快照可支持的状态。未返回的阶段不会被标记为已完成。</p>' +
      '</section>';
  }

  const api = {escapeHtml:escapeHtml, normalizeStatus:normalizeStatus, summarize:summarize, render:render, stages:STAGES};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.AgentFlowVisualization = api;
})(typeof window === 'undefined' ? globalThis : window);