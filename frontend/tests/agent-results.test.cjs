const {test} = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../agent-results.js');

const result = (tool, data, success = true) => ({tool, success, data, message: '', error: success ? null : '读取失败 <unsafe>'});
const doc = (name, id) => ({file_id:id, filename:name, path:'E:/任意课程/'+name});
function group(overrides = {}) {
    return {group_id:'version_group_001', documents:[doc('课程报告_v1.txt','one'),doc('课程报告_v2.txt','two')],
        grouping:{basis:'后端分组证据'}, comparison_order:{basis:'explicit_version',chronology_confirmed:false},
        newest_candidate:null, recommendation_reason:'insufficient_evidence', changes:[], ...overrides};
}
test('not run, successful empty, failed and malformed results stay distinct', () => {
    for (const [render,key] of [[ui.versions,'groups'],[ui.conflicts,'conflicts'],[ui.requirements,'required_documents']]) {
        assert.match(render(undefined), /未执行/);
        assert.match(render(result('tool',{[key]:[]})), /执行成功/);
        assert.match(render(result('tool',null,false)), /工具执行失败/);
        assert.doesNotMatch(render(result('tool',null,false)), /执行成功/);
        assert.match(render(result('tool',{})), /结构不完整/);
        assert.match(render(result('tool',null,false)), /&lt;unsafe&gt;/);
    }
});
test('singleton and all six abstention/recommendation reasons display without ranking', () => {
    const labels = ['single_document','identical_content','insufficient_evidence','version_tie','opposing_time_signal','unique_highest_explicit_version'];
    for (const reason of labels) {
        const html = ui.versions(result('compare_versions',{groups:[group({recommendation_reason:reason})]}));
        assert.match(html,/未推荐最新版本/);
        assert.doesNotMatch(html,/工具执行失败/);
    }
    const html = ui.versions(result('compare_versions',{groups:[group({documents:[doc('个人总结.txt','one')],recommendation_reason:'single_document'})]}));
    assert.match(html,/1 个候选/);
    assert.match(html,/仅有一个候选/);
});
test('all version candidates and backend recommendation evidence retained, never confirmed', () => {
    const candidate = {...doc('课程报告_v2.txt','two'), reasons:['唯一最高显式版本','时间信息不可比较']};
    const html = ui.versions(result('compare_versions',{groups:[group({newest_candidate:candidate,recommendation_reason:'unique_highest_explicit_version'})]}));
    assert.match(html,/课程报告_v1.txt/); assert.match(html,/课程报告_v2.txt/);
    assert.match(html,/E:\/任意课程\//); assert.match(html,/尚未确认采用/);
    assert.match(html,/时间信息不可比较/); assert.doesNotMatch(html,/已确认采用|checked|selected=/);
});
test('adjacent change evidence is escaped with original paths, line ranges and absent sides', () => {
    const html = ui.versions(result('compare_versions',{groups:[group({changes:[{from:doc('a.txt','one'),to:doc('b.txt','two'),type:'insert',summary:'新增一行',before:null,after:{start_line:2,end_line:2,text:'<script>alert(1)</script>\n'}}]})]}));
    assert.match(html,/新增一行/); assert.match(html,/无对应文本/); assert.match(html,/行 2–2/);
    assert.match(html,/&lt;script&gt;/); assert.doesNotMatch(html,/<script>/);
});
test('conflict values and full sources render with arbitrary fields; no source is selected', () => {
    const source='E:\\very-long-workspace\\通知.pdf';
    const html = ui.conflicts(result('detect_conflicts',{conflicts:[{field:'deadline:答辩',values:[{value:'2026-10-20T18:00:00',source}],recommendation:'请人工确认'}]}));
    assert.ok(html.includes(source)); assert.match(html,/deadline:答辩/); assert.match(html,/请人工确认/);
    assert.match(ui.conflicts(result('detect_conflicts',{conflicts:[]})),/检查范围内未发现冲突/);
});
test('empty requirements are not completeness; nonempty requirements are not approvals', () => {
    assert.match(ui.requirements(result('extract_requirements',{required_documents:[]})),/不能据此判断材料齐全/);
    const html=ui.requirements(result('extract_requirements',{required_documents:['奖学金申请表','课程证明']}));
    assert.match(html,/奖学金申请表/);assert.match(html,/不表示材料已匹配或审核通过/);
});
test('latest tool lookup is independent of position and does not hide latest failure', () => {
    const earlier=result('compare_versions',{groups:[]}), failure=result('compare_versions',null,false);
    assert.equal(ui.latest([earlier,result('read_document',{}),failure],'compare_versions'),failure);
});
test('unfrozen tools get generic execution status without interpreting draft fields', () => {
    for (const documents of [[],[doc('a.txt','a')],[doc('a.txt','a'),doc('b.txt','b')]]) {
        const html=ui.otherResults([result('match_requirements',{matched:[{documents}],missing:[]})]);
        assert.match(html,/不推断未冻结数据的含义/); assert.doesNotMatch(html,/材料齐全|缺失材料|已确认采用/);
    }
    assert.match(ui.otherResults([result('match_requirements',null,false)]),/工具执行失败/);
});
