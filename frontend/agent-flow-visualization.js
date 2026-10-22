(function (root) {
  'use strict';

  const STAGES = [
    {key:'scan', title:'扫描工作空间', subtitle:'建立文件清单与基础元数据', col:1,row:1,path:'right', match:/list_files|scan_workspace|scan_files|list all files|扫描文件/i},
    {key:'identify', title:'识别关键材料', subtitle:'定位课程要求、报告、代码与实验数据', col:2,row:1,path:'right', match:/search_files|find_duplicates|extract_requirements|match_requirements|classif|identify|search|识别材料/i},
    {key:'read', title:'读取文档内容', subtitle:'提取可读取的正文与表格', col:3,row:1,path:'down', match:/read_document|extract_text|document_reader|读取文档/i},
    {key:'versions', title:'比对版本与核查冲突', subtitle:'分析候选版本、内容差异与规则冲突', col:3,row:2,path:'left', match:/compare_versions|detect_conflicts|version|比较版本|版本分析|核查冲突/i},
    {key:'plan', title:'生成整理方案', subtitle:'形成分类目录与文件归属', col:2,row:2,path:'left', match:/plan_task|generate_plan|build_package|package_preview|生成整理方案/i},
    {key:'approve', title:'确认整理方案', subtitle:'关键操作在执行前等待审批', col:1,row:2,path:'down', match:/approval|approve|preview_plan|确认方案/i},
    {key:'execute', title:'创建目录并复制', subtitle:'按已确认方案执行文件操作', col:1,row:3,path:'right', match:/create_directory|create_folder|copy_file|move_file|execute_operation|apply_operation|write_package_report|创建目录|复制文件/i},
    {key:'verify', title:'校验整理结果', subtitle:'检查目标文件与内容完整性', col:2,row:3,path:'right', match:/verify|checksum|sha.?256|hash|validation|校验|核验/i},
    {key:'result', title:'汇总整理结果', subtitle:'呈现执行记录与最终结果', col:3,row:3,path:'none', match:/final_report|summarize_results|result_report|汇总结果/i}
  ];

  const STATUS = {
    pending: {label:'待执行', symbol:'○', className:'pending'},
    running: {label:'进行中', symbol:'●', className:'running'},
    completed: {label:'已完成', symbol:'✓', className:'completed'},
    failed: {label:'失败', symbol:'!', className:'failed'},
    awaiting_approval: {label:'等待审批', symbol:'Ⅱ', className:'awaiting-approval'},
    awaiting_clarification: {label:'等待回答', symbol:'?', className:'awaiting-clarification'},
    skipped: {label:'已跳过', symbol:'—', className:'skipped'}
  };

  const TASK_STATUS = {
    created:'任务已创建', planning:'正在规划', executing:'执行中',
    verifying:'验证中', awaiting_approval:'等待审批', awaiting_clarification:'等待回答',
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

  function confirmedReport(snapshot, report) {
    if (!snapshot || snapshot.task?.status !== 'completed' || !snapshot.task.task_id ||
        !report || report.task_id !== snapshot.task.task_id || report.status !== 'completed' ||
        !['found_files','version_groups','conflicts','operations'].every(key => Array.isArray(report[key])) ||
        typeof report.summary !== 'string' || typeof report.package_path !== 'string') return null;
    if (!Array.isArray(snapshot.results) || snapshot.results.some(result => !result || Array.isArray(result) || typeof result !== 'object' || typeof result.tool !== 'string' || result.success !== true)) return null;
    if (snapshot.results.some(result=>result.tool==='verify_result' && result.data?.passed!==true)) return null;
    if (!Array.isArray(snapshot.plan?.steps) || snapshot.plan.task_id !== snapshot.task.task_id) return null;
    const confirmed = evidenceSteps(snapshot);
    if (confirmed.length !== snapshot.plan.steps.length || confirmed.some(step=>!['completed','skipped'].includes(step.status))) return null;
    if (report.package_path || report.package_unresolved !== undefined) {
      if (!root?.PackagePreview) return null;
      const gate = root.PackagePreview.inspectSnapshot(snapshot);
      if (gate.state !== 'provided' || !root.PackagePreview.inspect({...gate.input, report}).packageSucceeded) return null;
    }
    return report;
  }

  function evidenceSteps(snapshot) {
    const raw = asArray(snapshot?.plan?.steps);
    if (snapshot?.plan?.task_id !== snapshot?.task?.task_id) return [];
    const results = Array.isArray(snapshot?.results) ? snapshot.results : [];
    let cursor = 0, failed = false;
    return raw.map((step, index) => {
      const safe = {...step, result_indexes:[]};
      if (step.status === 'completed' || step.status === 'failed') {
        const record = results[cursor];
        if (!failed && record && record.tool === step.tool && typeof record.success === 'boolean') {
          safe.result_indexes.push(cursor); cursor++;
          let success = record.success;
          // One read step may expand to a batch; retain every batch outcome.
          if (step.tool === 'read_document' && raw[index + 1]?.tool !== 'read_document') {
            while (results[cursor]?.tool === 'read_document') {
              success = success && results[cursor].success === true; safe.result_indexes.push(cursor); cursor++;
            }
          }
          failed = !success;
          safe.status = success && step.status === 'completed' ? 'completed' : 'failed';
          if (step.tool === 'verify_result' && record.data?.passed !== true) safe.status = 'failed';
        } else {
          safe.status = step.status === 'failed' ? 'failed' : 'unknown';
          failed = true;
        }
      }
      return safe;
    });
  }

  function detailText(value) {
    try { return JSON.stringify(value, (_, item) => typeof item === 'bigint' ? item.toString() : item, 2); }
    catch (_) { return '记录格式异常，无法展示'; }
  }

  function stageDetails(stage, snapshot, evidence, report) {
    if (!snapshot?.task?.task_id) return '';
    let records = evidence.map(step => ({step_id:step.step_id, tool:step.tool, status:step.status,
      description:step.description, arguments:step.arguments,
      results:(step.result_indexes || []).map(index => ({result_index:index, result:snapshot.results[index]}))}));
    if (records.some(record => ['plan_package','build_package'].includes(record.tool))) {
      if (!root?.PackagePreview || root.PackagePreview.inspectSnapshot(snapshot).state !== 'provided') records = [{diagnostic:'Package 证据尚未确认，不展示文件映射'}];
    }
    if (stage.key === 'approve' && report) records = [{operations:report.operations,diagnostic:'服务端完成的受审批操作；不重建或生成历史授权令牌'}];
    else if (stage.key === 'approve') records = snapshot.task.status === 'awaiting_clarification'
      ? [{clarification:snapshot.clarification}]
      : [{preview_id:snapshot.preview_id, operations:snapshot.pending_operations}];
    if (stage.key === 'plan') records = snapshot.task.status === 'awaiting_approval' ? [{preview_id:snapshot.preview_id,operations:snapshot.pending_operations}] : [{plan:snapshot.plan}];
    if (stage.key === 'verify') records = asArray(snapshot.results).map((result,index)=>({result_index:index,result})).filter(record=>record.result.tool==='verify_result');
    if (stage.key === 'result') records = report ? [{report}] : [{diagnostic:'最终报告尚未生成或未通过当前任务证据校验'}];
    return '<details class="agent-flow-details"><summary>执行详情 · ' + records.length + ' 项记录</summary><pre>' + escapeHtml(detailText({task_id:snapshot.task.task_id,records})) + '</pre></details>';
  }

  function stageStatus(stage, snapshot, steps, report) {
    const taskStatus = snapshot && snapshot.task ? snapshot.task.status : '';
    if (stage.key === 'result' && report && report.status === 'completed') {
      return {key:'completed', label:'结果已生成', evidence:[]};
    }
    if (stage.key === 'plan' && report && taskStatus === 'completed') return {key:'completed',label:'本次计划已完成',evidence:[]};
    if (stage.key === 'approve' && report && taskStatus === 'completed' && report.operations.some(operation=>['create_folder','copy_file','move_file'].includes(operation?.tool) && operation.success===true)) return {key:'completed',label:'受审批操作已完成',evidence:[]};
    if (stage.key === 'plan' && taskStatus === 'awaiting_clarification') return {key:'pending', label:'待回答后生成方案', evidence:[]};
    if (stage.key === 'plan' && taskStatus === 'planning') return {key:'running', label:'正在规划', evidence:[]};
    if (stage.key === 'plan' && taskStatus === 'awaiting_approval' && snapshot && snapshot.plan && asArray(snapshot.plan.steps).length) {
      return {key:'completed', label:'计划已生成', evidence:[]};
    }
    if (stage.key === 'verify') {
      const latest = asArray(snapshot?.results).filter(result=>result.tool==='verify_result').at(-1);
      if (latest && (latest.success !== true || latest.data?.passed !== true)) return {key:'failed',label:'核验未通过',evidence:[]};
    }
    if (stage.key === 'verify' && report && taskStatus === 'completed') {
      const last = asArray(snapshot.results).at(-1);
      if (last?.tool === 'verify_result' && last.success === true && last.data?.passed === true && Array.isArray(last.data.checks) && last.data.checks.length && last.data.checks.every(check=>check?.passed===true)) return {key:'completed',label:'文件核验通过',evidence:[]};
    }
    const matches = steps.filter(function (step) {
      const searchable = typeof step.tool === 'string' ? step.tool : '';
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
      const label = stage.key === 'versions' && key === 'completed' && !matches.some(step => step.tool === 'detect_conflicts') ? '版本已分析，冲突未执行' : normalizeStatus(key).label;
      return {key:key, label, evidence:matches};
    }

    if (stage.key === 'scan' && snapshot && taskStatus === 'created') {
      return {key:'pending', label:'等待扫描', evidence:[]};
    }
    if (stage.key === 'approve' && taskStatus === 'awaiting_clarification') {
      return {key:'awaiting_clarification', label:'等待回答', evidence:[]};
    }
    if (stage.key === 'approve' && taskStatus === 'awaiting_approval') {
      return {key:'awaiting_approval', label:'等待审批', evidence:[]};
    }
    if (stage.key === 'plan' && snapshot && snapshot.plan && asArray(snapshot.plan.steps).length) {
      return {key:'pending', label:'尚无冻结执行方案', evidence:[]};
    }
    if (stage.key === 'plan' && snapshot && taskStatus === 'failed' && /planner|plan|model request/i.test(String(snapshot.error || ''))) {
      return {key:'failed', label:'规划失败', evidence:[]};
    }
    return {key:snapshot ? 'not-returned' : 'idle', label:snapshot ? '当前快照未返回' : '等待任务', evidence:[]};
  }

  function currentStageKey(snapshot, steps, report) {
    if (!snapshot || !snapshot.task) return null;
    const taskStatus = typeof snapshot.task.status === 'string' ? snapshot.task.status : '';
    const failedStep = steps.find(function (step) { return normalizeStatus(step.status).key === 'failed'; });
    const activeStep = steps.find(function (step) {
      const key = normalizeStatus(step.status).key;
      return key === 'running' || key === 'awaiting_approval';
    });

    function matchingStage(step) {
      if (!step) return null;
      const searchable = typeof step.tool === 'string' ? step.tool : '';
      const match = STAGES.find(function (stage) { return stage.match.test(searchable); });
      return match ? match.key : null;
    }

    if (taskStatus === 'awaiting_approval' || taskStatus === 'awaiting_clarification') return 'approve';
    if (taskStatus === 'failed') {
      const failedStage = matchingStage(failedStep);
      if (failedStage) return failedStage;
      const errorText = [snapshot.error, snapshot.task.error, snapshot.message].filter(Boolean).join(' ');
      if (/planner|plan|model request|connection failed/i.test(errorText)) return 'plan';
      return null;
    }
    const activeStage = matchingStage(activeStep);
    if (activeStage) return activeStage;
    if (taskStatus === 'created') return 'scan';
    if (taskStatus === 'planning') return 'plan';
    if (taskStatus === 'executing') {
      const nextStep = steps.find(function (step) { return normalizeStatus(step.status).key === 'pending'; });
      return matchingStage(nextStep) || 'execute';
    }
    if (taskStatus === 'verifying') return 'verify';
    if (taskStatus === 'completed') {
      if (report) return null;
      const lastCompleted = steps.slice().reverse().find(function (step) {
        return normalizeStatus(step.status).key === 'completed';
      });
      return matchingStage(lastCompleted);
    }
    return null;
  }

  function stageMarkup(stage, index, status, snapshot, activeStageKey, report) {
    if (stage.key === 'approve' && snapshot?.task?.status === 'awaiting_clarification') stage = {...stage,title:'确认材料用途',subtitle:'回答问题后继续规划，尚未请求文件操作批准'};
    const evidence = status.evidence || [];
    const actual = evidence.length
      ? '<div class="agent-flow-evidence">' + evidence.slice(0,2).map(function (step) {
          const description = step.description || step.tool || '步骤说明未提供';
          const tool = step.tool ? ' · ' + step.tool : '';
          return '<p title="' + escapeHtml(description) + '">' + escapeHtml(description) + '<small>' + escapeHtml(tool) + '</small></p>';
        }).join('') + (evidence.length > 2 ? '<small>另有 ' + (evidence.length - 2) + ' 个关联步骤</small>' : '') + '</div>'
      : '<div class="agent-flow-stage-hint">' + (status.key === 'completed' ? '已由当前任务的服务端记录确认，展开查看详情。' : snapshot ? '等待此阶段的实际记录。' : '开始任务后显示状态') + '</div>';
    const meta = evidence.length ? '<span class="agent-flow-tool-count">' + evidence.length + ' 个关联步骤</span>' : '';
    return '<article class="agent-flow-stage" role="listitem" data-stage="' + stage.key + '" data-status="' + status.key + '" data-current="' + (activeStageKey === stage.key ? 'true' : 'false') + '" data-path="' + stage.path + '" style="--flow-col:' + stage.col + ';--flow-row:' + stage.row + ';">' +
      '<div class="agent-flow-stage-top"><span class="agent-flow-stage-number">' + String(index + 1).padStart(2,'0') + '</span>' +
      '<span class="agent-flow-stage-state"><i aria-hidden="true">' + (STATUS[status.key] ? STATUS[status.key].symbol : '·') + '</i>' + escapeHtml(status.label) + '</span>' +
      (activeStageKey === stage.key ? '<span class="agent-flow-current-badge">当前环节</span>' : '') + '</div>' +
      '<div class="agent-flow-stage-icon" aria-hidden="true">' + ({scan:'▤',identify:'⌕',read:'▧',versions:'⇄',approve:'◇',execute:'▣',verify:'✓',result:'▤'}[stage.key] || '○') + '</div>' +
      '<strong class="agent-flow-stage-title">' + escapeHtml(stage.title) + '</strong>' +
      '<p class="agent-flow-stage-subtitle">' + escapeHtml(stage.subtitle) + '</p>' +
      actual + meta + stageDetails(stage, snapshot, evidence, report) + '<span class="agent-flow-arrow" aria-hidden="true"></span></article>';
  }

  function render(snapshot, mode, report) {
    const hasTask = Boolean(snapshot && snapshot.task && typeof snapshot.task === 'object');
    const task = hasTask ? snapshot.task : {};
    const steps = evidenceSteps(snapshot);
    report = confirmedReport(snapshot, report || snapshot?.final_report);
    const taskStatus = typeof task.status === 'string' ? task.status : '';
    const taskLabel = TASK_STATUS[taskStatus] || (taskStatus ? '任务状态：' + taskStatus : '等待 Agent 任务');
    const analysis = STAGES.slice(0, 4).map((stage, original) => ({stage, original,
      first: steps.findIndex(step => stage.match.test(typeof step.tool === 'string' ? step.tool : ''))}));
    analysis.sort((a,b) => (a.first < 0 ? Infinity : a.first) - (b.first < 0 ? Infinity : b.first) || a.original-b.original);
    const ordered = [...analysis.map(item => item.stage), ...STAGES.slice(4)].map((stage,index) => ({...stage,
      col:STAGES[index].col,row:STAGES[index].row,path:STAGES[index].path}));
    let stageStates = ordered.map(function (stage) {
      return {stage:stage, state:stageStatus(stage, hasTask ? snapshot : null, steps, report)};
    });
    const unused = report ? stageStates.filter(item => item.state.key === 'not-returned') : [];
    if (report) stageStates = stageStates.filter(item => item.state.key !== 'not-returned');
    stageStates = stageStates.map((item,index) => ({...item,stage:{...item.stage,
      col:Math.floor(index/3)%2===0 ? index%3+1 : 3-index%3,
      row:Math.floor(index/3)+1,
      path:index===stageStates.length-1?'none':index%3===2?'down':Math.floor(index/3)%2===0?'right':'left'}}));
    const counts = {completed:0,running:0,failed:0,awaiting:0,notReturned:0};
    stageStates.forEach(function (item) {
      const key = item.state.key;
      if (key === 'completed') counts.completed++;
      else if (key === 'running') counts.running++;
      else if (key === 'failed') counts.failed++;
      else if (key === 'awaiting_approval' || key === 'awaiting_clarification') counts.awaiting++;
      else if (key === 'not-returned') counts.notReturned++;
    });
    const modeLabel = mode === 'mock' ? 'Mock Mode · 模拟任务数据' : 'Real Mode · 实时任务状态';
    const percent = Math.round(counts.completed / stageStates.length * 100);
    const note = !hasTask
      ? '启动任务后，流程图将跟随任务计划与执行状态更新；灰色节点表示当前尚无对应步骤证据。'
      : '节点状态随实际执行更新；完成、等待或失败以节点文字和执行详情为准。';
    const activeStageKey = currentStageKey(hasTask ? snapshot : null, steps, report);
    const nodes = stageStates.map(function (item, index) {
      return stageMarkup(item.stage, index, item.state, hasTask ? snapshot : null, activeStageKey, report);
    }).join('');

    return '<section class="agent-flow" data-task-status="' + escapeHtml(taskStatus || 'idle') + '">' +
      '<div class="agent-flow-overview"><div><span class="agent-flow-task-label">课程材料整理流程</span><strong>' + escapeHtml(taskLabel) + '</strong></div><span class="agent-flow-mode">' + escapeHtml(modeLabel) + '</span></div>' +
      '<p class="agent-flow-note">' + escapeHtml(note) + '</p>' +
      '<div class="agent-flow-summary">' +
        '<span><strong>' + STAGES.length + '</strong> 个流程阶段</span>' +
        '<span><strong>' + counts.completed + '</strong> ' + '已有完成证据' + '</span>' +
        '<span><strong>' + counts.running + '</strong> 进行中</span>' +
        '<span><strong>' + counts.failed + '</strong> 失败</span>' +
        '<span><strong>' + counts.notReturned + '</strong> 当前快照未返回</span>' +
      '</div>' +
      '<div class="agent-flow-progress" role="progressbar" aria-label="有完成证据的流程阶段比例" aria-valuemin="0" aria-valuemax="' + stageStates.length + '" aria-valuenow="' + counts.completed + '"><span style="width:' + percent + '%"></span></div>' +
      '<div class="agent-flow-graph" role="list" aria-label="课程材料整理流程图">' + nodes + '</div>' +
      (unused.length ? '<details class="agent-flow-unused"><summary>本次未安排的能力</summary><p>' + unused.map(item=>escapeHtml(item.stage.title)).join('、') + '；未执行，不计为完成。</p></details>' : '') +
      '<p class="agent-flow-footnote">蓝色高亮标记当前环节，动态连线只表示正在执行。卡片颜色不代表执行成功，请查看节点状态和核验结果。未返回的阶段不会被标记为已完成。</p>' +
      '</section>';
  }

  const api = {escapeHtml:escapeHtml, normalizeStatus:normalizeStatus, summarize:summarize, evidenceSteps:evidenceSteps, confirmedReport:confirmedReport, render:render, stages:STAGES};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.AgentFlowVisualization = api;
})(typeof window === 'undefined' ? globalThis : window);