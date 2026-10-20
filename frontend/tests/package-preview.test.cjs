const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const view=require('../package-preview.js'),fixtures=require('../package-fixtures.js'),{createState}=require('../package-demo.js');
test('normal frozen plan is displayable, never authorizes',()=>{
    const d=fixtures.get();assert.deepEqual(view.inspect(d).errors,[]);assert.equal(view.inspect(d).formalApprovalEnabled,false);
    const html=view.render(d);for(const label of ['1. 冻结方案','2. 具体文件映射','3. 缺项与风险','4. 操作顺序','5. 冻结报告','等待审批','不代表用户确认选材'])assert.ok(html.includes(label),label);
});
test('all fixtures render conservatively without mutating input',()=>{
    for(const name of fixtures.names){const d=fixtures.get(name),before=JSON.stringify(d);assert.equal(typeof view.render(d),'string');assert.equal(JSON.stringify(d),before);assert.equal(view.inspect(d).formalApprovalEnabled,false);}
});
test('null, absent, wrong type and empty data do not imply success',()=>{
    for(const d of [undefined,null,{},42,'bad',...['null','missing','empty','wrong_type'].map(fixtures.get)]){assert.ok(view.inspect(d).errors.length);assert.doesNotThrow(()=>view.render(d));}
});
test('nested null and wrong types render without crashing',()=>{
    for(const key of ['selected_files','missing','unresolved','operations','analysis','report'])for(const value of [null,[],{},'bad',42]){
        const d=fixtures.get();d.planResult.data.plan[key]=value;assert.doesNotThrow(()=>view.render(d));if(!(Array.isArray(value)&&['missing','unresolved'].includes(key)))assert.ok(view.inspect(d).errors.length);
    }
});
test('long paths and invalid long digests remain visible but invalid',()=>{
    const d=fixtures.get('long');assert.ok(view.render(d).includes(d.planResult.data.plan.selected_files[0].source.path));assert.ok(view.inspect(d).errors.length);
});
test('multiple candidates are retained without automatic user selection',()=>{
    const d=fixtures.get();assert.match(view.render(d),/fixture_file_2/);assert.match(view.render(d),/报告_v2/);assert.equal(d.planResult.data.plan.selected_files.length,1);
});
test('missing and all four unresolved kinds remain visible',()=>{
    const html=view.render(fixtures.get('risks'));for(const s of ['签字页','selection_pending','version_undecided','conflict','analysis_not_run'])assert.ok(html.includes(s));
});
test('not-run analysis must have an explicit unresolved record',()=>{
    const d=fixtures.get();d.planResult.data.plan.analysis.compare_versions=null;assert.match(view.inspect(d).errors.join(),/未执行且缺少未决记录/);
});
test('failed latest analysis cannot be accepted away or replaced by older success',()=>{
    const d=fixtures.get();d.snapshot.results.push({tool:'compare_versions',success:false,data:null,error:'failed'});assert.match(view.inspect(d).errors.join(),/过期/);
});
test('partial failure preserves successes and exposes failure, never verifies success',()=>{
    const d=fixtures.get('partial'),m=view.inspect(d),html=view.render(d);assert.equal(m.writes.filter(w=>w.result.success).length,2);assert.match(html,/文件操作失败/);assert.match(html,/未确认通过/);assert.equal(m.build.success,false);
});
test('cleanup failure and unknown residual are visible as confirmed but unimplemented metadata',()=>{
    for(const name of ['cleanup_failed','unknown_residual']){const html=view.render(fixtures.get(name));assert.match(html,/后端尚未实现/);assert.match(html,/不等于已回滚/);assert.match(html,name==='cleanup_failed'?/owned_fragment/:/unknown/);}
});
test('incorrect indices and mismatched plan identity fail provenance checks',()=>{
    for(const name of ['bad_index','mismatch'])assert.match(view.inspect(fixtures.get(name)).errors.join(),/不一致/);
});
test('non-Package report may omit package_unresolved',()=>{
    const d=fixtures.get('non_package');assert.equal(view.inspect(d).isPackage,false);assert.doesNotMatch(view.inspect(d).errors.join(),/报告缺少 package_unresolved/);
});
test('Package success requires structured frozen risks and verified execution',()=>{
    assert.deepEqual(view.inspect(fixtures.get('success')).errors,[]);
    assert.match(view.inspect(fixtures.get('missing_unresolved')).errors.join(),/缺少 package_unresolved/);
    const d=fixtures.get('success');d.report.package_unresolved.items=[];assert.match(view.inspect(d).errors.join(),/冻结风险来源不一致/);
});
test('old success never masks current failure',()=>{
    const d=fixtures.get('stale_success'),m=view.inspect(d),e=d.snapshot.package_execution;
    assert.equal(d.snapshot.results[0].success,true);assert.notEqual(d.snapshot.results[0].data.plan_id,e.plan_id);
    assert.equal(d.planResult.data.plan.plan_id,e.plan_id);assert.equal(d.planResult.data.plan_sha256,e.plan_sha256);
    for(const slot of Object.values(d.planResult.data.plan.analysis))if(slot)assert.deepEqual(d.snapshot.results[slot.result_index],slot.result);
    for(const link of e.operation_results)assert.ok(d.snapshot.results[link.result_index]);
    assert.equal(d.snapshot.results[e.final_result_index].success,false);assert.equal(m.build,d.snapshot.results[e.final_result_index]);
    assert.equal(m.writes.length,3);assert.equal(m.writes[2].result.success,false);
    assert.deepEqual(m.errors,['当前任务失败；旧成功结果不能代表当前成功']);assert.match(view.render(d),/未确认通过/);
});
test('null or malformed task with execution displays incomplete data and no successful writes',()=>{
    for(const task of [null,undefined,42,[],{},'wrong',{task_id:'fixture_task'}]){
        const d=fixtures.get('success');d.planResult.data.plan.task=task;const before=JSON.stringify(d),html=view.render(d),m=view.inspect(d);
        assert.match(html,/方案数据不完整/);assert.match(html,/未确认通过/);assert.doesNotMatch(html,/文件操作执行成功/);assert.equal(m.writes.length,0);assert.equal(JSON.stringify(d),before);
    }
});
test('null operations plus historical success retain invalid records and current failure',()=>{
    for(const value of [null,42,'bad',{},undefined]){
        const d=fixtures.get('stale_success');d.planResult.data.plan.operations[0]=value;
        const html=view.render(d),m=view.inspect(d);assert.match(html,/执行记录不完整\/无效/);assert.match(html,/原始数据保留/);assert.match(html,/未确认通过/);assert.equal(m.build.success,false);assert.equal(m.writes.some(w=>w.result.tool==='create_folder'),false);
    }
});
test('malformed results, links, out-of-range and wrong tools are never successful operations',()=>{
    for(const change of [d=>d.snapshot.results=null,d=>d.snapshot.results={},d=>d.snapshot.results[6]=null,d=>d.snapshot.results[6]=42,d=>d.snapshot.results[6]={tool:'copy_file',success:true},d=>d.snapshot.package_execution.operation_results[1]=null,d=>d.snapshot.package_execution.operation_results[1].result_index=999,d=>d.snapshot.results[6].tool='create_folder',d=>d.planResult.data.plan.selected_files[0].source=null]){
        const d=fixtures.get('success');change(d);const html=view.render(d),m=view.inspect(d);
        assert.match(html,/执行记录不完整\/无效/);assert.match(html,/未确认通过/);assert.equal(m.writes.some(w=>w.result.tool==='copy_file'),false);
    }
});
test('invalid unresolved provenance survives accepted UI intent without authorization or mutation',()=>{
    for(const change of [d=>d.planResult.data.plan.unresolved[0].source_result_index=999,d=>d.planResult.data.plan.unresolved[0].source_result_index=2,d=>d.planResult.data.plan.unresolved[0].source_result_index=-1,d=>d.planResult.data.plan.unresolved[0].source_result_index=true,d=>d.snapshot.results[1].success=false,d=>d.snapshot.results[1].tool='compare_versions',d=>d.snapshot.results.push({...d.snapshot.results[1],success:false,data:null,error:'latest failure'})]){
        const d=fixtures.get('risks');change(d);const state=createState();state.update('x',d);state.confirm(true);const before=JSON.stringify(d),html=view.render(d);
        assert.equal(state.accepted,true);assert.match(html,/未决事项来源关联无效/);assert.match(html,/selection_pending/);assert.match(html,/不作为已确认分析结论/);assert.equal(view.inspect(d).formalApprovalEnabled,false);assert.equal(d.snapshot.preview_id,null);assert.equal(JSON.stringify(d),before);
        state.update('another',fixtures.get());assert.equal(state.accepted,false);
    }
});
test('Package report without unresolved retains report facts but cannot claim verification success',()=>{
    const d=fixtures.get('missing_unresolved'),html=view.render(d);assert.match(html,/Package 报告缺少 package_unresolved/);assert.match(html,/未确认通过/);assert.ok(html.includes(d.report.package_path.replaceAll('\\','\\\\')));assert.equal(view.inspect(d).formalApprovalEnabled,false);
});
test('passed flag without required verification checks cannot claim verified success',()=>{
    const d=fixtures.get('success');d.snapshot.results[8].data.checks=[];assert.match(view.inspect(d).errors.join(),/验证检查缺失/);assert.match(view.render(d),/未确认通过/);
});
test('mismatched successful copy paths do not count as bound successful writes',()=>{
    const d=fixtures.get('success');d.snapshot.results[6].data.destination='different';const m=view.inspect(d);assert.match(m.errors.join(),/文件映射不一致/);assert.equal(m.writes.filter(w=>w.result.tool==='copy_file').length,0);
});
test('confirmation expires on fixture, plan id, digest or content change',()=>{
    const state=createState(),d=fixtures.get();state.update('a',d);state.confirm(true);assert.equal(state.update('a',d),true);
    for(const mutate of [()=>state.update('b',d),()=>{d.planResult.data.plan.plan_id+='x';state.update('b',d);},()=>{d.planResult.data.plan_sha256+='x';state.update('b',d);},()=>{d.planResult.data.plan.missing.push('new');state.update('b',d);}]){state.confirm(true);mutate();assert.equal(state.accepted,false);}
    assert.equal(d.snapshot.preview_id,null);
});
test('external HTML is escaped including frozen report and errors',()=>{
    const d=fixtures.get('partial'),evil='<img src=x onerror="pwned=true">&\'';d.planResult.data.plan.report.content=evil;d.snapshot.error=evil;d.planResult.data.plan.selected_files[0].reason=evil;
    const html=view.render(d);assert.doesNotMatch(html,/<img|<script/);assert.match(html,/&lt;img/);assert.match(html,/&quot;/);assert.match(html,/&#39;/);
});
test('presentation and fixture controller contain no network or filesystem calls',()=>{
    const original=global.fetch;global.fetch=()=>{throw Error('Network forbidden');};try{for(const name of fixtures.names)view.render(fixtures.get(name));}finally{global.fetch=original;}
    for(const name of ['package-preview.js','package-fixtures.js','package-demo.js']){const code=fs.readFileSync(path.join(__dirname,'..',name),'utf8');assert.doesNotMatch(code,/\b(fetch|XMLHttpRequest|AgentAPI|WebSocket)\s*[.(]|require\(['"](?:node:)?(?:fs|http|https|child_process)/);}
    const html=fs.readFileSync(path.join(__dirname,'../package-preview.html'),'utf8');assert.match(html,/id="formalApprove" disabled/);
});
test('unknown risk arrays remain risks and production Real Mode never loads Fixture code',()=>{
    for(const key of ['missing','unresolved']){const d=fixtures.get();d.planResult.data.plan[key]=null;assert.equal(view.inspect(d).hasRisks,true);assert.match(view.render(d),/数据不完整/);}
    for(const name of ['index.html','agent-api.js','agent-results.js'])assert.doesNotMatch(fs.readFileSync(path.join(__dirname,'..',name),'utf8'),/PackageFixtures|PackageDemo|package-fixtures\.js|package-demo\.js/);
});
