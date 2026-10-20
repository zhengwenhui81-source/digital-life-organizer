/* Local UI view model only, NOT a public ToolResult or a classification consumer.
 * No IO, classification, ranking, approval, or filesystem operations belong here. */
(function (root) {
    const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const text = value => typeof value === 'string' && value.trim().length > 0;
    const segments = value => Array.isArray(value) && value.length > 0 && value.length <= 32 && value.every(s => text(s) && s !== '.' && s !== '..' && !/[\\/]/.test(s));
    const item = body => '<div class="agent-item">' + body + '</div>';
    const note = value => '<p class="agent-note">' + escape(value) + '</p>';
    const path = value => '<p class="org-path">' + escape(value) + '</p>';
    const heading = value => '<h3>' + escape(value) + '</h3>';
    const evidenceKinds = {file_type:'按文件类型归类', filename:'文件名线索（演示）', text:'可读取文本线索（演示）'};
    function valid(data) {
        return data && data.localPreview === true && text(data.outputRoot) && ['windows','posix'].includes(data.pathStyle)
            && Array.isArray(data.folders) && data.folders.every(segments)
            && Array.isArray(data.categories) && data.categories.every(c => text(c?.name) && Array.isArray(c.files) && c.files.every(f =>
                text(f?.filename) && text(f.source) && segments(f.target) && text(f.reason) && Object.hasOwn(evidenceKinds,f.evidenceKind)))
            && ['pending','excluded'].every(key => Array.isArray(data[key]) && data[key].every(f => text(f?.filename) && text(f.source) && text(f.reason)));
    }
    function destination(data, parts) {
        const separator = data.pathStyle === 'windows' ? '\\' : '/';
        return data.outputRoot.replace(/[\\/]+$/, '') + separator + parts.join(separator);
    }
    function analyze(data) {
        if (data == null) return {state:'not_started'};
        if (!valid(data)) return {state:'incomplete'};
        const files = data.categories.flatMap(c => c.files.map(f => ({...f,category:c.name})));
        const key = parts => data.pathStyle === 'windows' ? parts.join('\\').toLowerCase() : parts.join('/');
        const folders = new Map();
        const addParents = (parts, includeLast) => {
            for (let i=1;i<=parts.length-(includeLast?0:1);i++) {
                const part=parts.slice(0,i); if(!folders.has(key(part))) folders.set(key(part),part);
            }
        };
        data.folders.forEach(p => addParents(p,true));
        files.forEach(f => addParents(f.target,false));
        const targets = new Map();
        files.forEach(f => {const k=key(f.target); if(!targets.has(k))targets.set(k,[]);targets.get(k).push(f);});
        const conflicts = [...targets.values()].filter(group => group.length > 1 || folders.has(key(group[0].target)));
        // Build a display tree from supplied target segments, never infer categories.
        const tree = {name:data.outputRoot,folders:new Map(),files:[]};
        function folder(parts) {
            let node=tree;
            for (const name of parts) {const k=key([name]);if(!node.folders.has(k))node.folders.set(k,{name,folders:new Map(),files:[]});node=node.folders.get(k);}
            return node;
        }
        folders.forEach(parts => folder(parts));
        files.forEach(f => folder(f.target.slice(0,-1)).files.push(f));
        return {state:'demo',files,folders:[...folders.values()],conflicts,tree};
    }
    function treeHtml(node, isRoot=false) {
        return '<details class="org-tree-node"' + (isRoot?' open':'') + '><summary>📁 ' + escape(node.name) + '</summary><ul>'
            + [...node.folders.values()].map(child => '<li>' + treeHtml(child) + '</li>').join('')
            + node.files.map(f => '<li>📄 ' + escape(f.target.at(-1)) + '</li>').join('')
            + (!node.folders.size && !node.files.length ? '<li class="agent-note">空文件夹</li>' : '') + '</ul></details>';
    }
    function render(data) {
        const model=analyze(data);
        if(model.state==='not_started')return '<p class="agent-note">尚未开始。选择本地 UI 场景，再点击“加载演示预览”。不会扫描 Workspace。</p>';
        if(model.state==='incomplete')return '<p class="result-warning" role="alert">预览数据结构不完整，无法可靠展示整理方案。请切换完整的本地演示数据；这不是分类工具失败，也没有执行文件操作。</p>';
        const categories = data.categories.map(c => item('<h4>' + escape(c.name) + ' · ' + c.files.length + ' 个文件</h4>'
            + (c.files.length ? c.files.map(f => item('<strong>' + escape(f.filename) + '</strong>' + note('原始路径') + path(f.source)
                + note('建议目标路径（未执行）') + path(destination(data,f.target)) + note(evidenceKinds[f.evidenceKind] + '：' + f.reason))).join('') : note('该分类没有文件。')))).join('');
        const pending = data.pending.map(f => item('<strong>' + escape(f.filename) + '</strong>' + path(f.source) + note(f.reason) + '<p class="result-warning">待人工确认 · 不参与自动整理</p>')).join('');
        const excluded = data.excluded.map(f => item('<strong>' + escape(f.filename) + '</strong>' + path(f.source) + note(f.reason))).join('');
        return '<p class="org-demo-badge">本地 UI 演示预览 · 非 Workspace 扫描结果</p>'
            + '<div class="org-summary">' + model.files.length + ' 个分类文件 · ' + data.categories.length + ' 个分类 · ' + data.pending.length + ' 个待确认 · ' + model.conflicts.length + ' 组可能冲突</div>'
            + '<div class="org-grid"><section class="org-panel">' + heading('分类结果') + (categories || note('分类结果为空；未对真实文件作出判断。')) + '</section>'
            + '<section class="org-panel">' + heading('文件夹目录树 · 仅预览') + note('点击文件夹展开或折叠。目录来自本地预览数据。') + treeHtml(model.tree,true) + '</section></div>'
            + '<section class="org-panel">' + heading('待人工确认材料') + (pending || note('本演示数据没有待确认项；不代表真实材料均已确定。')) + '</section>'
            + '<section class="org-panel">' + heading('拟执行的操作 · 默认复制') + '<p class="result-warning">当前仅展示整理方案，尚未执行文件操作。</p>'
            + heading('可能存在的同名或文件夹目标冲突') + (model.conflicts.map(group => item('<p class="result-warning">可能冲突 · 不会覆盖或自动选择</p>' + path(destination(data,group[0].target)) + group.map(f => path(f.source)).join(''))).join('') || note('本地预览未发现重复目标；不代表磁盘目标不存在，尚未进行后端验证。'))
            + heading('将创建的文件夹（预览）') + (model.files.length || model.folders.length ? item(note('目标根目录（存在性未验证）') + path(data.outputRoot)) + model.folders.map(p => item(path(destination(data,p)))).join('') : note('没有拟创建的文件夹。'))
            + heading('将复制的文件（预览）') + (model.files.map(f => item('<strong>复制 · ' + escape(f.filename) + '</strong>' + note('来源') + path(f.source) + note('目标') + path(destination(data,f.target)))).join('') || note('没有拟复制的文件。'))
            + heading('不参与自动整理的文件') + (pending + excluded || note('本地数据没有列出排除项。')) + '</section>';
    }
    // Stable TaskSnapshot metadata only. Classification payload is deliberately
    // opaque until a team-approved contract exists; never pass it to demo render.
    function inspectSnapshot(snapshot,expectedTask){
        const base={state:'blocked',taskStatus:null,approvalEnabled:false};
        if(snapshot==null)return base;
        const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
        const invalid=()=>({...base,state:'invalid'});
        if(!object(snapshot)||!object(snapshot.task)||!Array.isArray(snapshot.results)
            ||!object(expectedTask)||['task_id','user_goal','workspace'].some(k=>!text(expectedTask[k])||snapshot.task[k]!==expectedTask[k])
            ||!['created','planning','awaiting_approval','executing','verifying','completed','failed'].includes(snapshot.task.status)
            ||snapshot.results.some(r=>!object(r)||!text(r.tool)||typeof r.success!=='boolean'||!Object.hasOwn(r,'data')||typeof r.message!=='string'||!Object.hasOwn(r,'error')))return invalid();
        return {...base,taskStatus:snapshot.task.status};
    }
    function renderSnapshot(snapshot,expectedTask){
        const model=inspectSnapshot(snapshot,expectedTask);
        return '<p class="result-warning" role="status">正式整理模式 · 分类接口待团队确认，当前不能启动分类、审批或复制。</p>'
            + (model.state==='invalid'?note('数据异常或任务归属无法确认；不展示任何文件映射。'):note('真实分类数据尚未接入，不使用本地演示或 Package 结果补齐。'))
            + note(model.taskStatus?'关联任务状态：'+model.taskStatus+'；任务完成不代表分类或整理验证通过。':'尚未启动正式整理任务。')
            + '<div class="org-grid"><section class="org-panel">'+heading('分类目录与源/目标路径')+note('待正式契约提供分类目录、源路径、目标路径和分类依据；当前均未提供。')+'</section>'
            + '<section class="org-panel">'+heading('未确定文件与需要确认的类别')+note('待真实分析，不代表没有待确认文件；文件名或扩展名不是用途证明。')+'</section></div>'
            + '<section class="org-panel">'+heading('重名冲突、危险路径与执行风险')+note('尚未执行后端风险检查，不能显示为无风险。目标占用、越界路径、链接和覆盖风险须由后端校验。')
            + note('默认方案应为复制到独立目标；不移动、删除或覆盖原文件。前端不生成分类、权威摘要或审批凭据。')+'</section>';
    }
    const api={analyze,render,destination,inspectSnapshot,renderSnapshot};
    if(typeof module!=='undefined' && module.exports)module.exports=api;else root.OrganizationPreview=api;
})(typeof window==='undefined'?globalThis:window);
