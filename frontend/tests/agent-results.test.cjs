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
        const html=ui.otherResults([result('build_package',{example:[{documents}]})]);
        assert.match(html,/不推断未冻结数据的含义/); assert.doesNotMatch(html,/材料齐全|缺失材料|已确认采用/);
    }
    assert.match(ui.otherResults([result('build_package',null,false)]),/工具执行失败/);
});

test('matching distinguishes absent, failed, empty requirements and all unmatched',()=>{
    assert.match(ui.matching(undefined),/未执行/);
    const failure=result('match_requirements',null,false);failure.error='候选输入冲突 <bad>';
    assert.match(ui.matching(failure),/候选输入冲突 &lt;bad&gt;/);assert.match(ui.matching(failure),/工具执行失败/);
    assert.match(ui.matching(result('match_requirements',{required_documents:[],matched:[],missing:[]})),/没有明确的材料要求/);
    const html=ui.matching(result('match_requirements',{required_documents:['a','b'],matched:[],missing:['a','b']}));
    assert.match(html,/2 项本次未找到文件名候选/);assert.match(html,/不等于 Workspace/);assert.doesNotMatch(html,/工具执行失败|材料齐全/);
});
test('matching preserves exact references, all 1/N candidates, and backend order without selecting',()=>{
    const documents=[{file_id:'file_z',filename:'申请表_v2.txt',path:'E:\\unknown\\申请表_v2.txt'},{file_id:'file_a',filename:'申请表.txt',path:'E:\\unknown\\申请表.txt'}];
    const value=result('match_requirements',{required_documents:['申请表','单个'],matched:[{requirement:'申请表',documents},{requirement:'单个',documents:[documents[1]]}],missing:[]});
    const before=JSON.stringify(value), html=ui.matching(value);
    assert.ok(html.indexOf('file_z')<html.indexOf('file_a'));
    for(const d of documents)for(const key of ['filename','path','file_id'])assert.ok(html.includes(d[key]));
    assert.match(html,/2 个文件名候选/);assert.match(html,/1 个文件名候选/);assert.match(html,/候选材料，尚未审核/);
    assert.doesNotMatch(html,/selected=|checked|推荐最新/);assert.equal(JSON.stringify(value),before);
});
test('matching rejects incomplete or contradictory shapes rather than claiming empty success',()=>{
    for(const data of [{required_documents:[]},{required_documents:['a'],matched:[],missing:[]},{required_documents:['a'],matched:[{requirement:'a',documents:[]}],missing:[]},{required_documents:[],matched:[],missing:['a']},{required_documents:['a'],matched:[{requirement:'a',documents:[{filename:'a',path:'x'}]}],missing:[]}]){
        assert.equal(ui.matchingState(result('match_requirements',data)).kind,'unavailable');
    }
});
test('matching escapes requirement, file identity, filename, path and error',()=>{
    const evil='<img src=x onerror="alert(1)">';
    const html=ui.matching(result('match_requirements',{required_documents:[evil],matched:[{requirement:evil,documents:[{file_id:evil,path:evil,filename:evil}]}],missing:[]}));
    assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img/);
});
test('matching report requires latest success; never falls back or assumes empty report completeness',()=>{
    const success=result('match_requirements',{required_documents:['a'],matched:[],missing:['a']}), failure=result('match_requirements',null,false);
    assert.match(ui.matchingReport([success],[]),/不一致/);assert.match(ui.matchingReport([success],['a']),/本次未找到文件名候选/);
    const html=ui.matchingReport([success,failure],[]);assert.match(html,/工具执行失败/);assert.match(html,/不能解释 missing_items/);
    assert.doesNotMatch(html,/匹配执行成功/);assert.match(ui.matchingReport([],[]),/未执行/);
    assert.doesNotMatch(ui.otherResults([success]),/match_requirements/);
});

test('empty requirements and all requirements with candidates have distinct report meanings',()=>{
    const empty=result('match_requirements',{required_documents:[],matched:[],missing:[]});
    assert.match(ui.matchingReport([empty],[]),/没有明确的材料要求/);
    assert.doesNotMatch(ui.matchingReport([empty],[]),/每项要求均有/);
    const reference={file_id:'file_same',filename:'申请表_v1_v2.txt',path:'E:\\unknown\\申请表_v1_v2.txt'};
    const matched=result('match_requirements',{required_documents:['申请表_v1','申请表_v1_v2'],matched:[{requirement:'申请表_v1',documents:[reference]},{requirement:'申请表_v1_v2',documents:[reference]}],missing:[]});
    const html=ui.matchingReport([matched],[]);assert.match(html,/每项要求均有文件名候选/);
    assert.equal((html.match(/file_same/g)||[]).length,2);assert.match(html,/不代表材料已审核通过/);
});
