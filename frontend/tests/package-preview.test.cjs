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
const reverseKeys=value=>Array.isArray(value)?value.map(reverseKeys):value!==null&&typeof value==='object'?Object.fromEntries(Object.keys(value).reverse().map(k=>[k,reverseKeys(value[k])])):value;
test('reordered object keys preserve analysis, unresolved, operations and conflict equality without mutation',()=>{
    const d=fixtures.get('success');
    d.snapshot.results=d.snapshot.results.map(reverseKeys);d.report=reverseKeys(d.report);
    const before=structuredClone(d),m=view.inspect(d),html=view.render(d);
    assert.deepEqual(m.errors,[]);assert.match(html,/通过（仅文件检查）/);assert.equal(m.formalApprovalEnabled,false);assert.deepEqual(d,before);
});
test('structural comparison distinguishes missing, null, undefined, types, values and array order',()=>{
    const cases=[
        [{value:null},{}],[{value:undefined},{}],[{value:null},{value:undefined}],
        [{value:1},{value:'1'}],[{value:false},{value:0}],[{value:1},{value:2}],
        [{value:[1,2]},{value:[2,1]}],[{value:[]},{value:{}}]
    ];
    for(const [left,right] of cases){
        const d=fixtures.get('risks'),slot=d.planResult.data.plan.analysis.match_requirements;
        slot.result.data.extra=left;d.snapshot.results[slot.result_index].data.extra=right;
        const before=structuredClone(d),html=view.render(d),m=view.inspect(d);
        assert.match(m.errors.join(),/分析来源不一致/);assert.match(html,/未决事项来源关联无效/);assert.equal(m.formalApprovalEnabled,false);assert.deepEqual(d,before);
    }
});
test('reordered objects do not relax frozen array order or identity and index checks',()=>{
    const changes=[
        d=>d.report.package_unresolved.items.reverse(),
        d=>d.report.operations.reverse(),
        d=>delete d.report.package_unresolved.items[0].text,
        d=>d.report.package_unresolved.items[0].text=null,
        d=>d.snapshot.task.task_id='another_task',
        d=>d.snapshot.package_execution.plan_id='another_plan',
        d=>d.snapshot.package_execution.plan_sha256='sha256:'+'0'.repeat(64),
        d=>d.planResult.data.plan.analysis.match_requirements.result_index='1',
        d=>d.planResult.data.plan.unresolved[0].source_tool='compare_versions'
    ];
    for(const change of changes){
        const d=fixtures.get('success');d.report=reverseKeys(d.report);change(d);
        const m=view.inspect(d),html=view.render(d);assert.ok(m.errors.length);assert.match(html,/未确认通过/);assert.equal(m.formalApprovalEnabled,false);
    }
});

function rejectsVerifiedDisplay(data,warning){
    const before=structuredClone(data),m=view.inspect(data),html=view.render(data);
    assert.match(m.errors.join(),warning);assert.match(html,warning);
    assert.match(html,/文件验证：未确认通过/);assert.doesNotMatch(html,/文件验证：通过/);
    assert.equal(m.formalApprovalEnabled,false);assert.deepEqual(data,before);
    return m;
}

test('failed, absent, null, wrong-type and nonterminal report statuses never show verification success',()=>{
    for(const status of ['failed','executing','completed ',null,undefined,42,{},[]]){
        const d=fixtures.get('success');d.report.status=status;
        rejectsVerifiedDisplay(d,/Package 报告状态无效/);
    }
    const d=fixtures.get('success');delete d.report.status;rejectsVerifiedDisplay(d,/Package 报告状态无效/);
    for(const value of [false,0,'',42,'bad',[]]){const invalid=fixtures.get('success');invalid.report=value;rejectsVerifiedDisplay(invalid,/FinalReport 数据不完整\/无效/);}
});

test('verification targets require the exact ordered selected-file coverage and true flags',()=>{
    for(const value of [undefined,null,[],42,{}, {selected_file_indices:[],report:true,exact_directory_entries:true},
        {selected_file_indices:['0'],report:true,exact_directory_entries:true},
        {selected_file_indices:[0,0],report:true,exact_directory_entries:true},
        {selected_file_indices:[0],report:1,exact_directory_entries:true},
        {selected_file_indices:[0],report:true,exact_directory_entries:null},
        {selected_file_indices:[0],report:true,exact_directory_entries:true,extra:'invalid'}]){
        const d=fixtures.get('success');d.planResult.data.plan.verification_targets=value;
        rejectsVerifiedDisplay(d,/verification_targets 缺失或无效/);
    }
    const d=fixtures.get('partial');d.planResult.data.plan.verification_targets.selected_file_indices.reverse();
    rejectsVerifiedDisplay(d,/verification_targets 缺失或无效/);
});

test('full task context must match before any execution record is attributed',()=>{
    for(const field of ['task_id','user_goal','workspace'])for(const value of [undefined,null,'different',42]){
        const d=fixtures.get('success');d.snapshot.task[field]=value;
        assert.equal(rejectsVerifiedDisplay(d,/任务上下文不一致/).writes.length,0);
    }
});

test('task statuses and current terminal execution must agree even without a report',()=>{
    for(const status of [undefined,null,'unknown',42,'executing','failed']){
        const d=fixtures.get('success');d.report=null;d.snapshot.task.status=status;
        rejectsVerifiedDisplay(d,/任务状态/);
    }
    const d=fixtures.get('partial');d.snapshot.task.status='completed';
    rejectsVerifiedDisplay(d,/任务状态与当前 Package 执行结果不一致/);
    const pending=fixtures.get('partial');pending.snapshot.package_execution.final_result_index=null;
    pending.snapshot.task.status='executing';pending.snapshot.error=null;
    assert.doesNotMatch(view.render(pending),/文件验证：通过/);
});

test('cleanup observations require one complete record per attempted copy',()=>{
    const changes=[
        d=>delete d.snapshot.package_execution.cleanup_results,
        ...[null,{},42,[],[null],[{}]].map(value=>d=>d.snapshot.package_execution.cleanup_results=value),
        d=>delete d.snapshot.package_execution.cleanup_results[0].reason,
        d=>d.snapshot.package_execution.cleanup_results[0].reason=null,
        d=>d.snapshot.package_execution.cleanup_results[0].status='rolled_back',
        d=>d.snapshot.package_execution.cleanup_results[0].residual_state='deleted',
        d=>d.snapshot.package_execution.cleanup_results[0].step_id='package_001',
        d=>d.snapshot.package_execution.cleanup_results.push({...d.snapshot.package_execution.cleanup_results[0]}),
        d=>d.snapshot.package_execution.cleanup_results[0].extra='unexpected'
    ];
    for(const change of changes){const d=fixtures.get('success');change(d);rejectsVerifiedDisplay(d,/cleanup_results/);}
    rejectsVerifiedDisplay(fixtures.get('invalid_cleanup'),/cleanup_results 与已尝试复制关联不完整/);
});

test('cleanup state contradictions stay visible and cannot imply rollback or successful verification',()=>{
    for(const [status,residual_state] of [['succeeded','unknown'],['failed','absent'],['not_attempted','owned_fragment']]){
        const d=fixtures.get('partial');Object.assign(d.snapshot.package_execution.cleanup_results[1],{status,residual_state});
        rejectsVerifiedDisplay(d,/cleanup_results 与复制结果或残留状态矛盾/);
    }
    const d=fixtures.get('success');d.snapshot.package_execution.cleanup_results[0].status='succeeded';
    rejectsVerifiedDisplay(d,/cleanup_results 与复制结果或残留状态矛盾/);
});

test('consistent failure fixtures retain both copy observations and correct current indices',()=>{
    for(const name of ['partial','stale_success','cleanup_failed','unknown_residual']){
        const d=fixtures.get(name),e=d.snapshot.package_execution,m=view.inspect(d);
        const copies=e.operation_results.filter(link=>d.snapshot.results[link.result_index].tool==='copy_file');
        assert.equal(copies.length,2);assert.deepEqual(e.cleanup_results.map(c=>c.step_id),copies.map(c=>c.step_id));
        const cleanupWarning=name==='cleanup_failed'?'清理尝试失败：保留原始复制错误和清理原因，不表示已回滚':name==='unknown_residual'?'清理残留状态未知：不能确认对象已移除，不表示已回滚':null;
        assert.deepEqual(m.errors,[...(cleanupWarning?[cleanupWarning]:[]),'当前任务失败；旧成功结果不能代表当前成功']);
        assert.equal(m.build,d.snapshot.results[e.final_result_index]);assert.equal(m.build.success,false);
        assert.equal(d.report,null);assert.match(view.render(d),/首次复制文件保留/);
    }
    assert.match(fixtures.get('cleanup_failed').snapshot.package_execution.cleanup_results[1].reason,/removal attempt failed/);
    assert.match(fixtures.get('unknown_residual').snapshot.package_execution.cleanup_results[1].reason,/no removal attempted/);
});

test('unsafe nanoseconds remain unknown even when JSON parsing collapses different integers',()=>{
    const left=JSON.parse('{"mtime_ns":1792310400000000000}'),right=JSON.parse('{"mtime_ns":1792310400000000001}');
    assert.equal(left.mtime_ns,right.mtime_ns);assert.equal(Number.isSafeInteger(left.mtime_ns),false);
    const d=fixtures.get('success');d.planResult.data.plan.selected_files[0].snapshot.mtime_ns=left.mtime_ns;
    rejectsVerifiedDisplay(d,/纳秒时间戳超出 JavaScript 安全整数范围/);
    rejectsVerifiedDisplay(fixtures.get('unsafe_timestamp'),/精度无法确认/);
    const analysis=fixtures.get('success'),slot=analysis.planResult.data.plan.analysis.match_requirements;
    slot.result.data.extra=left;analysis.snapshot.results[slot.result_index].data.extra=right;
    rejectsVerifiedDisplay(analysis,/分析来源不一致/);
    for(const value of [null,undefined,'1792310400000000000',1.5,NaN,Infinity]){
        const invalid=fixtures.get('success');invalid.planResult.data.plan.selected_files[0].snapshot.mtime_ns=value;
        rejectsVerifiedDisplay(invalid,/文件快照时间或摘要格式不正确/);
    }
    assert.deepEqual(view.inspect(fixtures.get('success')).errors,[]);
});

test('terminal and verification indices require current ordered numeric execution links',()=>{
    for(const value of [null,undefined,-1,999,'9',true]){
        const d=fixtures.get('success');d.snapshot.package_execution.final_result_index=value;
        rejectsVerifiedDisplay(d,/执行结果|最终结果索引/);
    }
    const d=fixtures.get('success');d.snapshot.results[9].data.verification_result_index='8';
    rejectsVerifiedDisplay(d,/最终执行结果来源不一致/);
    const early=fixtures.get('success');early.snapshot.package_execution.operation_results[0].result_index=9;
    rejectsVerifiedDisplay(early,/最终执行结果来源不一致/);
    const afterFailure=fixtures.get('success');afterFailure.snapshot.results[6]={tool:'copy_file',success:false,data:null,message:'failed',error:'synthetic copy failure'};
    rejectsVerifiedDisplay(afterFailure,/失败后仍有后续操作记录/);
});
