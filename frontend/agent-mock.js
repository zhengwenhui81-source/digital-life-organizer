/* Demonstration only: never reads or changes user files. */
window.AgentMock = (() => {
    const tasks = new Map();
    const clone = value => JSON.parse(JSON.stringify(value));
    const definitions = [
        ['search_files', '搜索报名相关材料', 'low'],
        ['extract_requirements', '提取比赛要求', 'low'],
        ['compare_versions', '比较项目介绍版本', 'low'],
        ['detect_conflicts', '检查通知冲突及材料缺失', 'low'],
        ['copy_file', '复制最新项目介绍至报名资料包', 'medium'],
        ['move_file', '归档旧版本项目介绍', 'medium'],
        ['verify_result', '验证资料包并生成报告', 'low']
    ];
    const presentationDefinitions = [
        ['list_files', '扫描工作空间中的全部材料', 'low'],
        ['search_files', '识别课程要求与关键材料', 'low'],
        ['read_document', '读取要求文档和候选报告', 'low'],
        ['compare_versions', '比较报告版本与内容差异', 'low'],
        ['plan_task', '生成分类目录与文件归属方案', 'low'],
        ['preview_plan', '整理方案进入确认阶段（演示）', 'low'],
        ['copy_file', '模拟将材料复制到分类目录', 'medium'],
        ['verify_result', '模拟核对目标材料与源材料', 'low'],
        ['final_report', '汇总整理过程与检查结果', 'low']
    ];
    function find(id) {
        const record = tasks.get(id);
        if (!record) throw new Error('Mock task not found');
        return record;
    }
    function createTask({user_goal, workspace, scenario = 'happy'}) {
        if (!user_goal.trim() || !workspace.trim()) throw new Error('Workspace and goal are required');
        const task_id = 'mock_' + Date.now() + '_' + tasks.size;
        const path = name => workspace.replace(/[\\/]+$/, '') + '/' + name;
        const presentation = scenario === 'presentation';
        const filenames = presentation
            ? ['课程设计_提交要求.docx', '实验报告_v1.docx', '实验报告_最终版.docx', 'main.cpp', '实验数据.csv', '运行截图.png', '环境配置说明.md', '历史版本.zip', '临时笔记.txt']
            : ['项目介绍_v1.docx', '项目介绍_最终版.docx', '比赛通知.pdf', '补充通知.pdf', '报名表.docx', '学生证.pdf', '身份证.pdf'];
        const documents = filenames.map((filename, i) => ({file_id: 'file_' + i, path: path(filename), filename, extension: filename.slice(filename.lastIndexOf('.')), text: '', size: 12345, modified_time: i === 0 ? '2026-10-12T10:00:00' : '2026-10-14T18:00:00', metadata: {}}));
        const groups = presentation
            ? [{group_id: 'version_group_001', documents: documents.slice(1, 3), newest_candidate: documents[2].file_id, changes: ['最终版补充实验结果与结论（模拟）']}]
            : [{group_id: 'version_group_001', documents: documents.slice(0, 2), newest_candidate: documents[1].file_id, changes: ['补充项目方案与团队介绍（Mock）']}];
        const conflicts = presentation
            ? [{field: '报告版本', values: [{value: '实验报告_v1.docx', source: '历史版本'}, {value: '实验报告_最终版.docx', source: '版本比较'}], recommendation: '演示中优先选择最终版，正式任务需核对正文与提交要求'}]
            : [{field: 'deadline', values: [{value: '2026-10-18', source: '比赛通知.pdf'}, {value: '2026-10-20', source: '补充通知.pdf'}], recommendation: '请人工确认'}];
        const required_documents = presentation
            ? ['课程设计提交要求', '实验报告', '源代码', '实验数据', '运行截图']
            : ['报名表', '学生证', '身份证', '项目介绍', '指导教师确认书'];
        const operations = presentation
            ? [{tool: 'copy_file', source: documents[2].path, destination: path('分类整理/报告材料/实验报告_最终版.docx'), status: 'pending'}, {tool: 'copy_file', source: documents[3].path, destination: path('分类整理/源代码/main.cpp'), status: 'pending'}]
            : [{tool: 'copy_file', source: documents[1].path, destination: path('Hackathon_Package/项目介绍.docx'), status: 'pending'}, {tool: 'move_file', source: documents[0].path, destination: path('archive/项目介绍_v1.docx'), status: 'pending'}];
        const selectedDefinitions = presentation ? presentationDefinitions : definitions;
        const steps = selectedDefinitions.map(([tool, description, risk], i) => ({
            step_id: 'step_' + i, tool, description, risk, status: 'pending',
            arguments: tool === 'copy_file' || tool === 'move_file'
                ? {source: operations[tool === 'copy_file' ? 0 : 1]?.source, destination: operations[tool === 'copy_file' ? 0 : 1]?.destination}
                : tool === 'list_files' ? {workspace, extensions: []}
                : tool === 'search_files' ? {workspace, query: user_goal}
                : {}
        }));
        const tool = (name, data) => ({success: true, tool: name, data, message: 'Mock demonstration', error: null});
        tasks.set(task_id, {task: {task_id, user_goal, workspace, status: 'created'}, plan: {task_id, goal: user_goal, steps}, results: [], missing_items: [], operations, report: null, error: null, tick: 0, executionTick: 0, scenario, documents, groups, conflicts, required_documents, tool});
        return clone(find(task_id).task);
    }
    function getTask(id) {
        const r = find(id), s = r.plan.steps;
        if (r.scenario === 'presentation') {
            r.tick++;
            const stageIndex = r.tick - 1;
            if (stageIndex >= s.length) {
                r.task.status = 'completed';
                s.forEach(step => step.status = 'completed');
                r.operations.forEach(operation => operation.status = 'completed');
                r.results = [
                    r.tool('search_files', {documents: r.documents}),
                    r.tool('extract_requirements', {required_documents: r.required_documents}),
                    r.tool('compare_versions', {groups: r.groups}),
                    r.tool('detect_conflicts', {conflicts: r.conflicts}),
                    r.tool('plan_task', {steps: s}),
                    r.tool('preview_plan', {operations: r.operations, simulated: true}),
                    r.tool('copy_file', {simulated: true, note: '前端演示，没有复制真实文件'}),
                    r.tool('verify_result', {simulated: true, note: '前端演示，没有读取或校验真实文件'}),
                    r.tool('final_report', {simulated: true})
                ];
                r.report = {
                    task_id: id, status: 'completed', found_files: r.documents, version_groups: r.groups,
                    conflicts: r.conflicts, missing_items: [], operations: r.operations, package_path: null,
                    summary: '前端演示流程已完成：展示了扫描、识别、读取、版本比较、方案生成、文件操作与结果核验各阶段。未调用真实模型、未读取或修改工作空间中的文件。'
                };
            } else {
                s.forEach((step, i) => { step.status = i < stageIndex ? 'completed' : i === stageIndex ? 'running' : 'pending'; });
                r.task.status = stageIndex < 5 ? 'planning' : stageIndex < 7 ? 'executing' : 'verifying';
                const completed = s.slice(0, stageIndex).map(step => {
                    const data = step.tool === 'compare_versions' ? {groups: r.groups}
                        : step.tool === 'detect_conflicts' ? {conflicts: r.conflicts}
                        : step.tool === 'extract_requirements' ? {required_documents: r.required_documents}
                        : {simulated: true, note: '前端演示数据'};
                    return r.tool(step.tool, data);
                });
                r.results = completed;
            }
        } else if (['created', 'planning'].includes(r.task.status)) {
            r.tick++;
            r.task.status = 'planning';
            s.forEach((step, i) => { if (i < 4) step.status = i < r.tick - 1 ? 'completed' : i === r.tick - 1 ? 'running' : 'pending'; });
            if (r.scenario === 'failed' && r.tick === 2) {
                r.task.status = 'failed'; s[1].status = 'failed'; r.error = '模拟分析失败：无法解析比赛通知。没有执行文件操作。';
            } else if (r.tick >= 5) {
                r.task.status = 'awaiting_approval'; s[4].status = s[5].status = 'awaiting_approval';
                r.results = [r.tool('compare_versions', {groups: r.groups}), r.tool('detect_conflicts', {conflicts: r.conflicts}), r.tool('extract_requirements', {required_documents: r.required_documents})];
                r.missing_items = ['指导教师确认书'];
            }
        } else if (r.task.status === 'executing') {
            r.executionTick++;
            s[4].status = r.executionTick === 1 ? 'running' : 'completed';
            s[5].status = r.executionTick === 2 ? 'running' : r.executionTick > 2 ? 'completed' : 'pending';
            if (r.executionTick >= 3) { r.task.status = 'verifying'; s[6].status = 'running'; }
        } else if (r.task.status === 'verifying') {
            r.task.status = 'completed'; s[6].status = 'completed';
            r.operations.forEach(o => o.status = 'completed');
            r.report = {task_id: id, status: 'completed', found_files: r.documents, version_groups: r.groups, conflicts: r.conflicts, missing_items: r.missing_items, operations: r.operations, package_path: 'E:\\Hackthon\\demo\\sample_workspace\\Hackathon_Package', summary: 'Mock 演示完成：仍有截止日期冲突和一项缺失材料。未创建真实资料包，也未修改文件。'};
        }
        return clone({task: r.task, plan: r.plan, results: r.results, missing_items: r.missing_items, operations: r.results.length ? r.operations : [], error: r.error});
    }
    function approveTask(id) {
        const r = find(id);
        if (r.task.status !== 'awaiting_approval') throw new Error('Task is not awaiting approval');
        r.task.status = 'executing'; r.plan.steps[4].status = 'running'; r.plan.steps[5].status = 'pending';
        return clone(r.task);
    }
    function rejectTask(id) {
        const r = find(id);
        if (r.task.status !== 'awaiting_approval') throw new Error('Task is not awaiting approval');
        r.task.status = 'failed'; r.error = '用户取消了 Mock 操作；没有文件被修改。';
        r.plan.steps.filter(s => s.status !== 'completed').forEach(s => s.status = 'skipped');
        return clone(r.task);
    }
    function getReport(id) {
        const r = find(id);
        if (!r.report) throw new Error('Report is not ready');
        return clone(r.report);
    }
    return {createTask, getTask, approveTask, rejectTask, getReport};
})();
