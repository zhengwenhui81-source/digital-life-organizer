/* Loaded ONLY by demo/run_offline_browser.py, never by production index.html. */
(function () {
    const context = document.getElementById('offlineContext');
    if (!context) return;
    const scenarios = JSON.parse(context.textContent);
    const banner = document.createElement('aside');
    banner.id = 'offlineBanner';
    banner.style.cssText = 'position:sticky;top:0;z-index:1000;background:#172b43;color:#fff;border-bottom:3px solid #f39c12;padding:12px 24px;overflow-wrap:anywhere';
    const title = document.createElement('strong');
    title.textContent = '离线浏览器联调 · 固定 Planner · 非 LLM 推理 · 只读';
    const explanation = document.createElement('p');
    explanation.textContent = 'Real Mode 表示使用真实本地 HTTP 和分析工具，不表示 LLM 规划成功。自然语言仅作为任务标签；固定步骤不解释指令。只有本次临时测试目录可用，不生成材料包。';
    const label = document.createElement('label');
    label.textContent = '临时 Workspace 场景：';
    const select = document.createElement('select');
    select.id = 'offlineScenario';select.className = 'filter-select';
    for (const scenario of scenarios) {
        const option = document.createElement('option');option.value = scenario.name;option.textContent = scenario.label;select.appendChild(option);
    }
    label.appendChild(select);banner.append(title, explanation, label);document.body.prepend(banner);
    // The production sticky header must not cover the persistent offline label.
    document.querySelector('header').style.position = 'static';
    const mode = document.getElementById('agentMode');
    mode.value = 'real';mode.dispatchEvent(new Event('change'));
    mode.style.pointerEvents = 'none';mode.setAttribute('aria-disabled','true');mode.tabIndex = -1;
    document.getElementById('agentWorkspacePath').readOnly = true;
    document.getElementById('agentGoal').value = '离线固定步骤：提取要求、查找文件名候选、比较版本（非 LLM）';
    function choose() {
        if (agentState.busy || agentState.pollInFlight || agentState.decisionBusy) return;
        const scenario = scenarios.find(s => s.name === select.value);
        document.getElementById('agentWorkspacePath').value = scenario.workspace;
        stopAgentPolling();agentState.generation++;
        Object.assign(agentState,{task:null,snapshot:null,report:null,approvalValid:false,userRejected:false,mode:'real'});
        resetAgentPresentation();document.getElementById('agentTaskStatus').textContent = 'Ready · Real HTTP · Offline Fixed Planner';updateAgentControls();
    }
    select.addEventListener('change', choose);choose();
    // Production control logic owns task controls; constrain unrelated entrypoints
    // only in this injected development page, and keep the offline label visible.
    function lock() {
        select.disabled = agentState.busy || agentState.pollInFlight || agentState.decisionBusy;
        if (!mode.disabled) mode.disabled = true;
        for (const button of document.querySelectorAll('button')) {
            if (!['runAgent','refreshAgent','copyPackagePath'].includes(button.id) && !button.disabled) button.disabled = true;
        }
        document.getElementById('agentModeNote').textContent = '离线固定 Planner：真实 HTTP / 真实只读工具；不是 Mock，也不是 LLM 推理。';
    }
    new MutationObserver(lock).observe(document.getElementById('materialWorkspace'),{attributes:true,attributeFilter:['disabled'],subtree:true});
    lock();
})();
