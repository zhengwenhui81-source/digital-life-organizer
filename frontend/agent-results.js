/* Presentation only. Never rank, select, deduplicate, or authorize user files. */
(function (root) {
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const note = text => '<p class="agent-note">' + escape(text) + '</p>';
    const list = value => Array.isArray(value) ? value : [];
    const latest = (results, tool) => list(results).filter(r => r?.tool === tool).at(-1);
    function state(result, key) {
        if (!result) return {kind: 'not_run', html: note('未执行：尚未收到此工具的结果。')};
        if (result.success === false) return {kind: 'failed', html: '<p class="result-warning">工具执行失败</p>' + note(result.error || result.message || '未提供错误详情。')};
        if (result.success !== true || !Array.isArray(result.data?.[key])) return {kind: 'unavailable', html: note('结果结构不完整，暂时无法确认结果。')};
        return {kind: 'success', items: result.data[key]};
    }
    function reference(doc) {
        return '<div class="agent-item"><strong>' + escape(doc?.filename || '未提供文件名') + '</strong><p class="agent-path-text">' + escape(doc?.path) + '</p></div>';
    }
    const reasons = {
        single_document: '仅有一个候选，无可比较版本',
        identical_content: '提取文本相同，未推荐最新版本',
        insufficient_evidence: '显式版本证据不足',
        version_tie: '最高显式版本并列',
        opposing_time_signal: '版本与修改时间证据相互冲突',
        unique_highest_explicit_version: '唯一最高显式版本，无相反的可比较时间证据'
    };
    function excerpt(value, label) {
        if (value === null) return note(label + '：无对应文本');
        if (!value || typeof value.text !== 'string') return note(label + '：文本证据未提供');
        return '<div><small>' + escape(label) + ' · 行 ' + escape(value.start_line) + '–' + escape(value.end_line) + '</small><pre class="version-evidence">' + escape(value.text) + '</pre></div>';
    }
    function groups(items) {
        return items.map(group => {
            if (!group || !Array.isArray(group.documents)) return note('版本组结构不完整。');
            const candidate = group.newest_candidate;
            const recommended = candidate && typeof candidate === 'object' && typeof candidate.file_id === 'string';
            return '<section class="version-group"><h4>' + escape(group.group_id) + ' · ' + group.documents.length + ' 个候选</h4>' +
                group.documents.map(reference).join('') +
                (recommended ? '<p class="badge badge-neutral">后端版本推荐 · 尚未确认采用</p>' + reference(candidate) + list(candidate.reasons).map(note).join('') : '<p class="result-warning">未推荐最新版本</p>') +
                note('推荐依据：' + (reasons[group.recommendation_reason] || group.recommendation_reason || '尚未提供；不能据此确定最新版本')) +
                note('版本推荐不代表用户已确认，也不授权任何文件操作。') +
                note('分组依据：' + (group.grouping?.basis || '尚未提供')) +
                note('比较顺序：' + (group.comparison_order?.basis || '尚未提供') + '；不代表已确认的时间先后。') +
                list(group.changes).map(change => '<details class="version-change"><summary>' + escape(change?.summary || '文本差异') + '</summary>' +
                    note('类型：' + (change?.type || '未提供')) + reference(change?.from) + note('→') + reference(change?.to) +
                    excerpt(change?.before, '比较前') + excerpt(change?.after, '比较后') + '</details>').join('') + '</section>';
        }).join('');
    }
    function versions(result) {
        const outcome = state(result, 'groups');
        if (outcome.kind !== 'success') return outcome.html;
        return note('版本比较执行成功') + (outcome.items.length ? groups(outcome.items) : note('没有版本分组。未发现分组不等于已证明文件之间无关系。'));
    }
    function conflicts(result) {
        const outcome = state(result, 'conflicts');
        if (outcome.kind !== 'success') return outcome.html;
        if (!outcome.items.length) return note('冲突检查执行成功：在本次支持的检查范围内未发现冲突。');
        return note('冲突检查执行成功，请核对以下来源；系统不裁定哪个来源正确。') + outcome.items.map(c =>
            '<section class="agent-item"><h4 class="result-warning">' + escape(c?.field) + '</h4>' + list(c?.values).map(v =>
                '<div class="agent-item"><strong>' + escape(v?.value) + '</strong><p class="agent-path-text">' + escape(v?.source) + '</p></div>'
            ).join('') + note(c?.recommendation || '请人工确认') + '</section>').join('');
    }
    function requirements(result) {
        const outcome = state(result, 'required_documents');
        if (outcome.kind !== 'success') return outcome.html;
        if (!outcome.items.length) return note('要求提取执行成功：没有提取到明确必交要求，请核对通知。不能据此判断材料齐全。');
        return note('已提取必交要求；以下名称不表示材料已匹配或审核通过。') + outcome.items.map(name => '<div class="agent-item">• ' + escape(name) + '</div>').join('');
    }
    function matchingState(result) {
        const outcome = state(result, 'required_documents');
        if (outcome.kind !== 'success') return outcome;
        const data = result.data, string = value => typeof value === 'string' && value.trim().length > 0;
        const complete = Array.isArray(data.matched) && Array.isArray(data.missing)
            && data.required_documents.every(string) && data.missing.every(string)
            && data.matched.every(m => string(m?.requirement) && Array.isArray(m.documents) && m.documents.length > 0
                && m.documents.every(d => string(d?.file_id) && string(d.filename) && string(d.path)));
        if (complete) {
            const covered = [...data.matched.map(m => m.requirement), ...data.missing];
            if (new Set(data.required_documents).size === data.required_documents.length
                && new Set(covered).size === covered.length && covered.length === data.required_documents.length
                && covered.every(name => data.required_documents.includes(name))) return {...outcome, data};
        }
        return {kind:'unavailable', html:note('匹配结果结构不完整或要求对应关系不一致，暂时无法确认候选情况。')};
    }
    function matching(result) {
        const outcome = matchingState(result);
        if (outcome.kind !== 'success') return outcome.html;
        const data = outcome.data;
        const scope = note('Phase 1 仅建立文件名候选关系：未审核内容、签名、有效期或真实性；候选不代表审核通过，也不授权文件操作。');
        if (!data.required_documents.length) return scope + note('匹配执行成功：本次没有明确的材料要求，不能据此判断材料齐全。');
        return scope + note('匹配执行成功 · ' + data.required_documents.length + ' 项要求；' + data.matched.length + ' 项有文件名候选；' + data.missing.length + ' 项本次未找到文件名候选。')
            + data.matched.map(m => '<section class="agent-item"><h4>' + escape(m.requirement) + ' · ' + m.documents.length + ' 个文件名候选</h4>'
                + note(m.documents.length === 1 ? '候选材料，尚未审核。' : '保留全部候选及后端顺序；尚未选定最终版本。')
                + m.documents.map(d => reference(d) + note('file_id：' + d.file_id)).join('') + '</section>').join('')
            + data.missing.map(name => '<div class="agent-item"><strong>' + escape(name) + '</strong>' + note('本次未找到文件名候选；不等于 Workspace 中不存在证明材料或审核不通过。') + '</div>').join('');
    }
    function matchingReport(results, missingItems) {
        const result = latest(results, 'match_requirements'), outcome = matchingState(result);
        let html = '<h4>Matching Phase 1 · 最近工具结果</h4>' + matching(result);
        if (outcome.kind !== 'success') return html + note('报告缺项数组为空不代表已检查材料齐全；没有可用的成功匹配结果，不能解释 missing_items。');
        if (!Array.isArray(missingItems) || JSON.stringify(missingItems) !== JSON.stringify(outcome.data.missing))
            html += '<p class="result-warning">报告 missing_items 与最近成功匹配结果不一致或未提供，请核对后端报告；此处保留工具结果。</p>';
        if (outcome.data.required_documents.length && !outcome.data.missing.length)
            html += note('本次每项要求均有文件名候选；这不代表材料已审核通过。');
        return html;
    }
    function otherResults(results) {
        return list(results).filter(r => r && !['compare_versions','detect_conflicts','extract_requirements','match_requirements'].includes(r.tool)).map(r =>
            '<div class="agent-item"><strong>' + escape(r.tool) + '</strong>' + note(r.success === true ? '工具执行成功；此处不推断未冻结数据的含义。' : r.success === false ? '工具执行失败' : '执行状态未知') + note(r.error || r.message || '尚未提供详情。') + '</div>'
        ).join('');
    }
    const api = {latest, state, versions, conflicts, requirements, matchingState, matching, matchingReport, otherResults};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.AgentResults = api;
})(typeof window === 'undefined' ? globalThis : window);
