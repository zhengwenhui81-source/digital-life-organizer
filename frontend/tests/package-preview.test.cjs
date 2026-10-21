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
test('cleanup failure and unknown residual are visible as backend observations, never rollback proof',()=>{
    for(const name of ['cleanup_failed','unknown_residual']){const html=view.render(fixtures.get(name));assert.match(html,/后端实际返回记录/);assert.match(html,/不等于已回滚/);assert.match(html,name==='cleanup_failed'?/owned_fragment/:/unknown/);}
});
test('incorrect indices and mismatched plan identity fail provenance checks',()=>{
    for(const name of ['bad_index','mismatch'])assert.match(view.inspect(fixtures.get(name)).errors.join(),/不一致/);
});
test('non-Package report may omit package_unresolved',()=>{
    const d=fixtures.get('non_package');assert.equal(view.inspect(d).isPackage,false);assert.doesNotMatch(view.inspect(d).errors.join(),/报告缺少 package_unresolved/);
    assert.match(view.render(d),/非 Package 报告，不要求 package_unresolved/);assert.doesNotMatch(view.render(d),/报告未通过当前执行完整性检查/);
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

test('read-only progress distinguishes no execution, returned outcomes and unknown in-flight steps',()=>{
    const idle=view.inspect(fixtures.get('complete'));assert.equal(idle.packageSucceeded,false);
    assert.ok(idle.operationRows.every(row=>row.label.includes('未执行')));
    for(const name of ['executing','verifying']){
        const d=fixtures.get(name),before=structuredClone(d),m=view.inspect(d),html=view.render(d);
        assert.deepEqual(m.errors,[]);assert.equal(m.packageSucceeded,false);assert.match(html,/Package 执行中/);
        assert.ok(m.operationRows.some(row=>row.label.includes('尚无完成结果')));
        assert.equal(m.operationRows.filter(row=>row.result).length,name==='executing'?1:3);
        assert.doesNotMatch(html,/Package 执行与文件验证成功/);assert.deepEqual(d,before);
    }
    const missing=fixtures.get('complete');missing.snapshot.task.status='executing';
    assert.ok(view.inspect(missing).operationRows.every(row=>row.label.includes('不能推断未执行')));
});

test('partial failure exposes exact frozen paths and errors and never counts unattempted steps as successes',()=>{
    const d=fixtures.get('partial'),m=view.inspect(d),html=view.render(d),failed=m.operationRows[2];
    assert.equal(failed.source,d.planResult.data.plan.selected_files[1].source.path);
    assert.equal(failed.target,d.planResult.data.plan.selected_files[1].target);
    assert.equal(failed.result.data,null);assert.equal(failed.result.success,false);
    assert.match(html,/second copy failed/);assert.match(html,/部分操作成功，Package 任务失败/);
    assert.ok(m.operationRows.slice(3).every(row=>row.label.includes('未执行')&&!row.result));
    assert.equal(m.packageSucceeded,false);assert.equal(d.report,null);
});

test('cleanup labels distinguish removed fragments, failed cleanup and unknown residue without rollback claims',()=>{
    for(const [name,label,residual] of [['cleanup_succeeded','清理成功','无失败复制片段'],['cleanup_failed','清理失败','失败复制片段仍存在'],['unknown_residual','未尝试清理','未知残留']]){
        const d=fixtures.get(name),m=view.inspect(d),html=view.render(d),row=m.cleanupRows[1];
        assert.ok(row.label.includes(label));assert.ok(row.residual.includes(residual));
        assert.equal(m.packageSucceeded,false);assert.match(html,/不表示已回滚|不代表回滚/);
        assert.equal(m.cleanupRows[0].record.reason,'copy_succeeded');assert.match(m.cleanupRows[0].residual,/成功文件仍可能保留/);
    }
    const invalid=fixtures.get('cleanup_succeeded');invalid.snapshot.package_execution.cleanup_results.push({...invalid.snapshot.package_execution.cleanup_results[1]});
    const rows=view.inspect(invalid).cleanupRows.filter(row=>row.record.step_id==='package_003');
    assert.ok(rows.every(row=>row.label.includes('关联无效')));
});

test('Package completion requires current verified execution and full FinalReport while frozen risks survive',()=>{
    const good=fixtures.get('success'),m=view.inspect(good),html=view.render(good);
    assert.equal(m.packageSucceeded,true);assert.match(html,/Package 执行与文件验证成功；不代表材料内容合格/);
    for(const value of ['签字页','selection_pending','version_undecided','conflict','analysis_not_run'])assert.ok(html.includes(value));
    const noReport=fixtures.get('success');noReport.report=null;
    assert.equal(view.inspect(noReport).packageSucceeded,false);assert.match(view.render(noReport),/完成仍待完整证据与 FinalReport/);
    for(const change of [d=>delete d.report.summary,d=>d.report.summary='材料全部审核通过',d=>delete d.report.operations,d=>d.snapshot.results[9].data.generated_files=[],d=>d.snapshot.results[9].data.report_path='wrong']){
        const d=fixtures.get('success');change(d);assert.equal(view.inspect(d).packageSucceeded,false);
        assert.doesNotMatch(view.render(d),/Package 执行与文件验证成功/);
    }
});

test('verification failure remains failed even when all copies and report writes succeeded',()=>{
    const d=fixtures.get('verification_failed'),m=view.inspect(d),html=view.render(d);
    assert.equal(m.writes.length,3);assert.ok(m.writes.every(row=>row.result.success));
    assert.equal(m.verification.success,false);assert.equal(m.build.success,false);assert.equal(m.packageSucceeded,false);
    assert.match(html,/验证失败，Package 未成功/);assert.match(html,/digest verification failed/);
    assert.doesNotMatch(html,/文件验证：通过/);
    const flag=fixtures.get('verification_failed');flag.snapshot.results[8]={tool:'verify_result',success:true,data:{passed:false,checks:[]},message:'checks failed',error:null};
    assert.match(view.render(flag),/验证失败，Package 未成功/);
    assert.match(view.inspect(flag).operationRows[3].label,/验证结果已返回/);assert.doesNotMatch(view.inspect(flag).operationRows[3].label,/成功/);
});

test('stale terminal results, replaced planning records and cross-task data cannot confirm execution',()=>{
    const old=fixtures.get('success');old.snapshot.results.push({tool:'build_package',success:false,data:null,message:'new failure',error:'current failure'});
    assert.equal(view.inspect(old).packageSucceeded,false);assert.match(view.render(old),/终止结果已过期/);
    assert.ok(view.inspect(old).operationRows.every(row=>!row.result));
    const repl=fixtures.get('success'),plan=structuredClone(repl.planResult);plan.data.plan.plan_id='package_plan_'+'2'.repeat(32);repl.snapshot.results.push(plan);
    const m=view.inspect(repl);assert.equal(m.packageSucceeded,false);assert.equal(m.writes.length,0);assert.match(view.render(repl),/较新规划替代/);
    const foreign=fixtures.get('success');foreign.snapshot.task.task_id='foreign';
    assert.equal(view.inspect(foreign).packageSucceeded,false);assert.ok(view.inspect(foreign).operationRows.every(row=>!row.result));
    const polluted=fixtures.get('stale_success');assert.equal(view.inspect(polluted).packageSucceeded,false);
    assert.match(view.render(polluted),/部分操作成功，Package 任务失败/);
});

test('a failed directory excludes later successful copy, verify and build evidence but preserves diagnostics',()=>{
    const d=fixtures.get('success');d.snapshot.task.status='failed';d.report=null;
    d.snapshot.results[5]={tool:'create_folder',success:false,data:null,message:'mkdir failed',error:'exclusive directory failed'};
    const before=structuredClone(d),m=view.inspect(d),html=view.render(d);
    assert.deepEqual(m.boundOperations.map(row=>row.result_index),[5]);
    assert.deepEqual(m.writes.map(row=>row.result),[d.snapshot.results[5]]);
    assert.equal(m.verification,null);assert.equal(m.build,null);
    assert.deepEqual(m.anomalousResults.map(row=>row.result_index),[6,7,8,9]);
    assert.equal(m.boundOperations[0].result.error,'exclusive directory failed');
    assert.ok(m.operationRows.slice(1).every(row=>!row.evidenceValid&&row.result.success===true&&row.label==='失败后异常记录，不可作为有效执行证据'));
    assert.doesNotMatch(html,/文件操作执行成功|文件验证：通过/);
    assert.match(html,/exclusive directory failed/);assert.match(html,/copy_file/);assert.match(html,/build_package/);
    assert.ok(m.cleanupRows.every(row=>row.label==='清理记录不完整/关联无效'));
    assert.equal(m.packageSucceeded,false);assert.equal(m.formalApprovalEnabled,false);assert.deepEqual(d,before);
});

test('first copy failure excludes a later successful copy and its cleanup claim without losing the failure',()=>{
    const d=fixtures.get('partial'),second=d.planResult.data.plan.selected_files[1];
    d.snapshot.results[6]={tool:'copy_file',success:false,data:null,message:'first copy failed',error:'first copy source failure'};
    d.snapshot.results[7]={tool:'copy_file',success:true,data:{source:second.source.path,destination:second.target},message:'unexpected second copy success',error:null};
    d.snapshot.package_execution.cleanup_results[0]={step_id:'package_002',status:'not_attempted',reason:'source failure',residual_state:'absent'};
    d.snapshot.package_execution.cleanup_results[1]={step_id:'package_003',status:'succeeded',reason:'untrusted cleanup',residual_state:'absent'};
    const before=structuredClone(d),m=view.inspect(d);
    assert.deepEqual(m.boundOperations.map(row=>row.result_index),[5,6]);
    assert.deepEqual(m.writes.filter(row=>row.result.success).map(row=>row.result.tool),['create_folder']);
    assert.equal(m.operationRows[1].evidenceValid,true);assert.equal(m.operationRows[1].result.error,'first copy source failure');
    assert.equal(m.operationRows[2].evidenceValid,false);assert.equal(m.operationRows[2].result,d.snapshot.results[7]);
    assert.match(m.operationRows[2].label,/失败后异常记录/);assert.doesNotMatch(m.operationRows[2].label,/成功/);
    assert.equal(m.cleanupRows[1].label,'清理记录不完整/关联无效');assert.equal(m.cleanupRows[1].record.status,'succeeded');
    assert.equal(m.verification,null);assert.equal(m.build.success,false);assert.equal(m.packageSucceeded,false);
    const html=view.render(d);assert.match(html,/first copy source failure/);assert.match(html,/unexpected second copy success/);
    assert.deepEqual(d,before);
});

test('copy failure blocks later verify success and terminal build success independently',()=>{
    for(const terminalSuccess of [false,true]){
        const d=fixtures.get('success');d.snapshot.task.status='failed';d.report=null;
        d.snapshot.results[6]={tool:'copy_file',success:false,data:null,message:'copy failed',error:'copy failure evidence'};
        if(!terminalSuccess)d.snapshot.results[9]={tool:'build_package',success:false,data:null,message:'failed',error:'original failure retained'};
        const m=view.inspect(d),html=view.render(d);
        assert.deepEqual(m.boundOperations.map(row=>row.result_index),[5,6]);
        assert.equal(m.writes.filter(row=>row.result.success).length,1);
        assert.equal(m.verification,null);assert.equal(m.operationRows[3].evidenceValid,false);
        assert.equal(m.operationRows[3].result,d.snapshot.results[8]);
        assert.ok(m.anomalousResults.some(row=>row.result===d.snapshot.results[8]));
        if(terminalSuccess){assert.equal(m.build,null);assert.ok(m.anomalousResults.some(row=>row.result===d.snapshot.results[9]));}
        else assert.equal(m.build,d.snapshot.results[9]);
        assert.equal(m.packageSucceeded,false);assert.doesNotMatch(html,/文件验证：通过|Package 执行与文件验证成功/);
        assert.match(html,/copy failure evidence/);assert.equal(m.formalApprovalEnabled,false);
    }
});

test('valid complete chain still exposes only bound successful operations and confirms the report',()=>{
    const m=view.inspect(fixtures.get('success'));
    assert.deepEqual(m.boundOperations.map(row=>row.result_index),[5,6,7,8]);
    assert.equal(m.anomalousResults.length,0);assert.equal(m.writes.length,3);
    assert.ok(m.operationRows.every(row=>row.evidenceValid));
    assert.equal(m.verification.success,true);assert.equal(m.build.success,true);assert.equal(m.packageSucceeded,true);
});

test('new unbound verification invalidates old verification and FinalReport even when tool success is true',()=>{
    for(const mode of ['failed_checks','failed_tool','duplicate_success','foreign_scope','after_terminal']){
        const d=fixtures.get('success'),old=d.snapshot.results[8];
        const bad=structuredClone(old);
        if(mode==='failed_checks'||mode==='after_terminal'){bad.data.passed=false;bad.data.checks[0].passed=false;}
        if(mode==='failed_tool'){Object.assign(bad,{success:false,data:null,error:'new verification failed'});d.snapshot.task.status='failed';}
        if(mode==='foreign_scope')bad.data.checks[0].path='UNBOUND_OTHER_SCOPE';
        if(mode==='after_terminal')d.snapshot.results.push(bad);
        else {d.snapshot.results.splice(9,0,bad);d.snapshot.package_execution.final_result_index=10;}
        const before=structuredClone(d),m=view.inspect(d),html=view.render(d);
        assert.equal(m.verification,null,mode);assert.equal(m.build,null,mode);
        assert.deepEqual(m.boundOperations.map(row=>row.result_index),[5,6,7]);assert.equal(m.writes.length,3);
        assert.equal(m.operationRows[3].evidenceValid,false);assert.match(m.operationRows[3].label,/验证关联异常/);
        assert.ok(m.anomalousResults.some(row=>row.result===old));assert.ok(m.anomalousResults.some(row=>row.result===bad));
        assert.equal(m.packageSucceeded,false);assert.equal(m.formalApprovalEnabled,false);
        assert.match(html,/验证记录缺失、重复或关联不完整/);assert.match(html,/报告未通过当前执行完整性检查/);
        assert.doesNotMatch(html,/文件验证：通过|Package 执行与文件验证成功/);assert.deepEqual(d,before);
    }
});

test('missing or misindexed verify cannot be replaced by a successful terminal or report',()=>{
    for(const change of [d=>d.snapshot.package_execution.operation_results.pop(),d=>d.snapshot.package_execution.operation_results[3].result_index=7,d=>d.snapshot.results[8]=null]){
        const d=fixtures.get('success');change(d);const m=view.inspect(d),html=view.render(d);
        assert.equal(m.verification,null);assert.ok(m.boundOperations.every(row=>row.result.tool!=='verify_result'));
        assert.equal(m.packageSucceeded,false);assert.equal(m.operationRows[3].evidenceValid,false);
        assert.doesNotMatch(html,/文件验证：通过|Package 执行与文件验证成功/);
    }
});

test('report discovery and Version contents must match current complete source records',()=>{
    for(const field of ['found_files','version_groups']){
        const d=fixtures.get('success');d.report[field]=[{path:'OLD_FOREIGN_SOURCE',group_id:'FOREIGN_OLD_GROUP'}];
        const before=structuredClone(d),m=view.inspect(d),html=view.render(d);
        assert.notDeepEqual(m.reportSources[field],d.report[field]);assert.equal(m.packageSucceeded,false);
        assert.match(html,new RegExp('报告 '+field+' 来源'));assert.match(html,/报告未通过当前执行完整性检查/);
        assert.match(html,/OLD_FOREIGN_SOURCE/);assert.doesNotMatch(html,/Package 执行与文件验证成功/);assert.deepEqual(d,before);
    }
    const d=fixtures.get('success'),file={path:'E:\\虚构输入\\发现.txt',name:'合成发现',size:10};
    d.snapshot.results[0].data.files=[file];d.report.found_files=[structuredClone(file)];
    assert.equal(view.inspect(d).packageSucceeded,true);
    d.report.found_files[0].size='10';
    assert.equal(view.inspect(d).packageSucceeded,false); // Same path/name is not source equality.
});

test('missing failed stale or wrongly indexed sources never confirm a Package report',()=>{
    const changes=[
        d=>d.snapshot.results[0]={tool:'read_document',success:true,data:{},message:'no discovery',error:null},
        d=>d.snapshot.results[0].data.files=null,
        d=>d.snapshot.results.push(structuredClone(d.snapshot.results[0])),
        d=>{d.planResult.data.plan.analysis.compare_versions.result_index=999;d.snapshot.results[4]=structuredClone(d.planResult);},
        d=>{d.planResult.data.plan.analysis.compare_versions.result_index='3';d.snapshot.results[4]=structuredClone(d.planResult);},
        d=>d.snapshot.results[3]={tool:'read_document',success:true,data:{},message:'missing Version',error:null},
        d=>d.snapshot.results.push(structuredClone(d.snapshot.results[3])),
        d=>d.snapshot.results[3]={tool:'compare_versions',success:false,data:null,message:'Version failed',error:'source failed'},
        d=>d.snapshot.task.task_id='FOREIGN_TASK'
    ];
    for(const change of changes){
        const d=fixtures.get('success');change(d);const before=structuredClone(d),m=view.inspect(d),html=view.render(d);
        assert.equal(m.packageSucceeded,false);assert.ok(m.reportSources.found_files===null||m.reportSources.version_groups===null);
        assert.match(html,/报告未通过当前执行完整性检查/);assert.doesNotMatch(html,/Package 执行与文件验证成功/);
        assert.deepEqual(d,before);
    }
});

function unrunConflicts(){
    const d=fixtures.get('success'),p=d.planResult.data.plan;
    p.analysis.detect_conflicts=null;
    p.unresolved=p.unresolved.map(u=>u.source_tool==='detect_conflicts'?{kind:'analysis_not_run',source_tool:'detect_conflicts',source_result_index:null,documents:[],text:'Conflict analysis not run'}:u);
    d.report.package_unresolved.items=structuredClone(p.unresolved);d.report.conflicts=[];
    d.snapshot.results[2]={tool:'read_document',success:true,data:{},message:'no conflict analysis',error:null};
    d.snapshot.results[4]=structuredClone(d.planResult);
    return d;
}

test('explicit unrun conflict risk permits incomplete execution display without inferring authorization or no conflicts',()=>{
    const d=unrunConflicts(),before=structuredClone(d),m=view.inspect(d),html=view.render(d);
    assert.deepEqual(m.errors,[]);assert.equal(m.packageSucceeded,true);assert.equal(m.hasRisks,true);
    assert.deepEqual(m.reportSources.conflicts,[]);assert.equal(m.boundOperations.length,4);assert.equal(m.writes.length,3);
    assert.equal(m.authorizationConfirmed,false);assert.equal(m.formalApprovalEnabled,false);
    for(const text of ['analysis_not_run','Conflict analysis not run','签字页','打包执行成功，但材料包仍有缺项或未决事项','不确认服务端审批'])assert.ok(html.includes(text),text);
    assert.match(html,/Package 执行与文件验证成功；不代表材料内容合格/);assert.deepEqual(d,before);
    const pending=unrunConflicts();pending.snapshot.task.status='awaiting_approval';pending.snapshot.package_execution=null;pending.report=null;
    assert.equal(view.inspect(pending).packageSucceeded,false);assert.equal(view.inspect(pending).authorizationConfirmed,false);
});

test('missing conflict risk or erased report risks cannot pass as a legitimate incomplete plan',()=>{
    for(const mode of ['no_risk','missing_slot','erased_report','fake_conflicts']){
        const d=unrunConflicts(),p=d.planResult.data.plan;
        if(mode==='no_risk')p.unresolved=p.unresolved.filter(u=>u.source_tool!=='detect_conflicts');
        if(mode==='missing_slot')delete p.analysis.detect_conflicts;
        if(mode==='erased_report')d.report.package_unresolved.items=[];
        if(mode==='fake_conflicts')d.report.conflicts=[{field:'invented'}];
        d.snapshot.results[4]=structuredClone(d.planResult);
        const m=view.inspect(d),html=view.render(d);
        assert.equal(m.packageSucceeded,false);assert.equal(m.authorizationConfirmed,false);assert.equal(m.formalApprovalEnabled,false);
        assert.match(html,/报告未通过当前执行完整性检查/);assert.doesNotMatch(html,/Package 执行与文件验证成功/);
    }
});

function planningSnapshot(){
    const s=fixtures.get('complete').snapshot;s.task.status='planning';return s;
}
test('Snapshot adapter distinguishes absent real planning from malformed payloads',()=>{
    const s=planningSnapshot();s.results=s.results.filter(r=>r.tool!=='plan_package');
    assert.equal(view.inspectSnapshot(s).state,'unavailable');
    assert.match(view.renderSnapshot(s),/真实 Package 规划数据尚未提供/);
    assert.doesNotMatch(view.renderSnapshot(s),/数据格式异常/);
    for(const value of [{},{task:s.task,results:null},{task:s.task,results:[null]}]){
        assert.equal(view.inspectSnapshot(value).state,'invalid');assert.match(view.renderSnapshot(value),/格式异常|字段缺失/);
    }
});
test('Snapshot adapter renders current planning evidence with identity, preview and immutable order',()=>{
    const s=planningSnapshot();s.task.status='awaiting_approval';s.preview_id='server-preview';
    s.pending_operations=[{tool:'build_package',step_id:'build',arguments:{}}];
    const before=structuredClone(s),m=view.inspectSnapshot(s),html=view.renderSnapshot(s);
    assert.equal(m.state,'provided');assert.equal(m.resultIndex,4);assert.equal(m.input.planResult,s.results[4]);
    for(const value of ['server-preview','fixture_task','package_plan_','plan_sha256','结题报告.txt','多候选证据','选材为提议'])assert.ok(html.includes(value),value);
    assert.match(html,/批准时由后端复验绑定/);assert.deepEqual(s,before);
    delete s.preview_id;assert.match(view.renderSnapshot(s),/preview_id 尚未提供/);
});
test('Snapshot adapter never falls back from latest failure, missing manifest or later upstream failure',()=>{
    for(const latest of [{tool:'plan_package',success:false,data:null,message:'failed',error:'latest failed'},
        {tool:'plan_package',success:true,data:{},message:'missing plan',error:null},
        {tool:'read_document',success:false,data:null,message:'failed',error:'read failed'}]){
        const s=planningSnapshot();s.results.push(latest);const m=view.inspectSnapshot(s),html=view.renderSnapshot(s);
        assert.notEqual(m.state,'provided');assert.equal(m.input,null);assert.doesNotMatch(html,/提议文件 1/);
        assert.equal(m.resultIndex,latest.tool==='plan_package'?5:4);
    }
    const s=planningSnapshot();s.task.status='failed';s.error='current failed';
    assert.equal(view.inspectSnapshot(s).state,'failed');assert.match(view.renderSnapshot(s),/current failed/);
    assert.doesNotMatch(view.renderSnapshot(s),/具体文件映射/);
});
test('Snapshot adapter rejects foreign task contexts and expired analysis without leaking mappings',()=>{
    for(const key of ['task_id','user_goal','workspace']){
        const s=planningSnapshot(),expected={...s.task,[key]:'other'};
        assert.equal(view.inspectSnapshot(s,expected).state,'invalid');assert.doesNotMatch(view.renderSnapshot(s,expected),/结题报告.txt/);
        s.results[4].data.plan.task[key]='other';
        assert.equal(view.inspectSnapshot(s).state,'invalid');assert.doesNotMatch(view.renderSnapshot(s),/结题报告.txt/);
    }
    const s=planningSnapshot();s.results.push({...s.results[3]});
    assert.equal(view.inspectSnapshot(s).state,'invalid');assert.match(view.renderSnapshot(s),/过期/);
    assert.doesNotMatch(view.renderSnapshot(s),/具体文件映射/);
});
test('Snapshot adapter does not retain old plans between snapshots and marks missing preview evidence',()=>{
    const first=planningSnapshot();assert.equal(view.inspectSnapshot(first).state,'provided');
    const second=planningSnapshot();second.results=[];assert.equal(view.inspectSnapshot(second).state,'unavailable');
    const missing=planningSnapshot();delete missing.results[4].data.plan.selected_files;
    assert.equal(view.inspectSnapshot(missing).state,'invalid');assert.match(view.renderSnapshot(missing),/selected_files 不是数组/);
    const preview=planningSnapshot();preview.preview_id='server-preview';preview.pending_operations=[];
    assert.match(view.renderSnapshot(preview),/pending_operations/);
    preview.preview_id=42;assert.match(view.renderSnapshot(preview),/preview_id 格式异常/);
});
test('Snapshot adapter binds the displayed identity and preview to the latest planning record',()=>{
    const s=planningSnapshot(),next=structuredClone(s.results[4]);
    next.data.plan.plan_id='package_plan_'+'2'.repeat(32);next.data.plan_sha256='sha256:'+'e'.repeat(64);
    s.results.push(next);s.preview_id='new-server-preview';s.pending_operations=[{tool:'build_package',step_id:'build',arguments:{}}];
    const m=view.inspectSnapshot(s),html=view.renderSnapshot(s);
    assert.equal(m.state,'provided');assert.equal(m.resultIndex,5);assert.equal(m.input.planResult,next);
    assert.match(html,/new-server-preview/);assert.ok(html.includes(next.data.plan.plan_id));
    assert.ok(html.includes(next.data.plan_sha256));assert.ok(!html.includes(s.results[4].data.plan.plan_id));
});

test('malformed latest Package data is invalid without throwing, mutating or exposing historical mappings',()=>{
    const badData=[undefined,null,[],[{}],'bad',42,true,{},
        {plan:null,plan_sha256:'sha256:'+'a'.repeat(64)},
        {plan:[],plan_sha256:'sha256:'+'a'.repeat(64)},
        {plan:'bad',plan_sha256:'sha256:'+'a'.repeat(64)}];
    for(const data of badData){
        const s=planningSnapshot();s.results.push({tool:'plan_package',success:true,data,message:'malformed current result',error:null});
        const before=structuredClone(s);let model,html;
        assert.doesNotThrow(()=>{model=view.inspectSnapshot(s);html=view.renderSnapshot(s);});
        assert.equal(model.state,'invalid');assert.equal(model.resultIndex,5);assert.equal(model.input,null);
        assert.match(html,/data|ToolResult/);assert.match(html,/不使用历史成功/);
        assert.doesNotMatch(html,/提议文件 1|结题报告.txt|文件操作执行成功|文件验证：通过/);assert.deepEqual(s,before);
    }
});

test('invalid manifest and digest identities never enter detailed Snapshot rendering',()=>{
    const changes=[
        d=>delete d.plan,d=>delete d.plan_sha256,
        ...[undefined,null,[],{},42,true,'','bad'].map(value=>d=>d.plan_sha256=value),
        ...[undefined,null,[],42,true,'bad'].map(value=>d=>d.plan=value),
        ...[undefined,null,[],42,true,'bad'].map(value=>d=>d.plan.plan_id=value),
        d=>d.plan.task=null,d=>d.extra='unexpected'
    ];
    for(const change of changes){
        const s=planningSnapshot(),latest=structuredClone(s.results[4]);change(latest.data);s.results.push(latest);
        const before=structuredClone(s),m=view.inspectSnapshot(s),html=view.renderSnapshot(s);
        assert.equal(m.state,'invalid');assert.equal(m.input,null);assert.equal(m.resultIndex,5);
        assert.doesNotMatch(html,/结题报告.txt|具体文件映射|文件验证：通过/);assert.deepEqual(s,before);
    }
});

test('invalid source snapshots and superseded frozen indices expose diagnostics but no detailed mapping',()=>{
    for(const change of [s=>delete s.results[4].data.plan.selected_files[0].snapshot,
        s=>s.results.splice(4,0,structuredClone(s.results[3]))]){
        const s=planningSnapshot();s.task.status='awaiting_approval';s.preview_id='server-preview';
        s.pending_operations=[{tool:'build_package',step_id:'build',arguments:{}}];
        const file=structuredClone(s.results[4].data.plan.selected_files[0]);
        assert.equal(view.inspectSnapshot(s).state,'provided');change(s);
        const before=structuredClone(s),m=view.inspectSnapshot(s),html=view.renderSnapshot(s);
        assert.equal(m.state,'invalid');assert.equal(m.input,null);assert.match(html,/快照数据不完整|来源不一致或已过期/);
        for(const value of ['提议文件','具体文件映射',file.source.filename,file.source.path,file.target])assert.equal(html.includes(value),false,value);
        assert.doesNotMatch(html,/文件验证：通过|文件操作执行成功/);assert.deepEqual(s,before);
    }
});

test('all non-provided Snapshot states withhold detail while standalone Fixture diagnostics stay separate',()=>{
    const invalid=planningSnapshot();delete invalid.results[4].data.plan.selected_files[0].snapshot;
    const failed=planningSnapshot();failed.task.status='failed';failed.error='current failed';
    const unavailable=planningSnapshot();unavailable.results=[];
    for(const s of [invalid,failed,unavailable,null]){
        const m=view.inspectSnapshot(s),html=view.renderSnapshot(s);
        assert.ok(['invalid','failed','unavailable'].includes(m.state));assert.equal(m.input,null);
        assert.doesNotMatch(html,/提议文件|结题报告.txt|具体文件映射|冻结分析与多候选证据|文件验证：通过/);
    }
    const fixture=fixtures.get('complete');delete fixture.planResult.data.plan.selected_files[0].snapshot;
    assert.match(view.render(fixture),/快照数据不完整/);assert.match(view.render(fixture),/结题报告.txt/);
});

test('integrated Snapshot gateway retains valid execution progress but cannot invent a FinalReport',()=>{
    for(const name of ['executing','verifying','success']){
        const d=fixtures.get(name),before=structuredClone(d.snapshot),m=view.inspectSnapshot(d.snapshot),html=view.renderSnapshot(d.snapshot);
        assert.equal(m.state,'provided',name);assert.ok(html.includes(d.planResult.data.plan.selected_files[0].source.filename));
        const projected=view.inspect(m.input);
        assert.equal(projected.packageSucceeded,false);assert.equal(projected.formalApprovalEnabled,false);
        assert.equal(projected.authorizationConfirmed,false);assert.equal(m.input.report,undefined);
        if(name==='success'){
            assert.equal(projected.boundOperations.length,4);assert.match(html,/完成仍待完整证据与 FinalReport/);
        }else assert.match(html,/Package 执行中/);
        assert.doesNotMatch(html,/Package 执行与文件验证成功/);assert.deepEqual(d.snapshot,before);
    }
});

test('integrated Snapshot gateway withholds paths for failed execution, invalid verification and unknown cleanup',()=>{
    const newer=fixtures.get('success');
    const bad=structuredClone(newer.snapshot.results[8]);bad.data.passed=false;bad.data.checks[0].passed=false;
    newer.snapshot.results.splice(9,0,bad);newer.snapshot.package_execution.final_result_index=10;
    const badLink=fixtures.get('executing');badLink.snapshot.package_execution.operation_results[0].result_index='5';
    for(const d of [newer,badLink,fixtures.get('partial'),fixtures.get('cleanup_failed'),fixtures.get('unknown_residual')]){
        const before=structuredClone(d.snapshot),m=view.inspectSnapshot(d.snapshot),html=view.renderSnapshot(d.snapshot);
        assert.ok(['failed','invalid'].includes(m.state));assert.equal(m.input,null);
        for(const file of d.planResult.data.plan.selected_files)for(const value of [file.source.filename,file.source.path,file.target])assert.equal(html.includes(value),false,value);
        assert.doesNotMatch(html,/具体文件映射|文件操作执行成功|文件验证：通过|Package 执行与文件验证成功/);
        assert.deepEqual(d.snapshot,before);
    }
    assert.equal(view.inspect(newer).verification,null);assert.equal(view.inspect(newer).build,null);
});

function declareAnalysisNotRun(tool,removeExecution){
    const d=fixtures.get('success'),p=d.planResult.data.plan;
    const index=p.analysis[tool].result_index,field=tool==='compare_versions'?'version_groups':'conflicts';
    p.analysis[tool]=null;
    p.unresolved=p.unresolved.map(u=>u.source_tool===tool?{kind:'analysis_not_run',source_tool:tool,source_result_index:null,documents:[],text:tool+' explicitly not run'}:u);
    d.report[field]=[];d.report.package_unresolved.items=structuredClone(p.unresolved);
    if(removeExecution)d.snapshot.results[index]={tool:'read_document',success:true,data:{},message:'synthetic unrelated record; no analysis call',error:null};
    d.snapshot.results[4]=structuredClone(d.planResult);
    return {d,index,field};
}

for(const tool of ['compare_versions','detect_conflicts']){
    test(tool+' actual successful nonempty analysis cannot be hidden by null/not-run',()=>{
        const {d,index,field}=declareAnalysisNotRun(tool,false),before=structuredClone(d);
        const raw=d.snapshot.results[index],key=tool==='compare_versions'?'groups':'conflicts';
        assert.equal(raw.success,true);assert.ok(raw.data[key].length>0);
        const m=view.inspect(d),html=view.render(d),gate=view.inspectSnapshot(d.snapshot),safeHtml=view.renderSnapshot(d.snapshot);
        assert.equal(m.reportSources[field],null);assert.equal(m.packageSucceeded,false);
        assert.match(m.errors.join(),/分析来源矛盾/);assert.match(html,/分析来源矛盾/);
        assert.match(html,/报告未通过当前执行完整性检查/);
        assert.doesNotMatch(html,/Package 执行与文件验证成功|本次报告与关联执行证据一致|文件验证：通过/);
        assert.equal(gate.state,'invalid');assert.equal(gate.input,null);
        for(const file of d.planResult.data.plan.selected_files)for(const value of [file.source.filename,file.source.path,file.target])assert.equal(safeHtml.includes(value),false,value);
        assert.equal(d.snapshot.results[index],raw);assert.equal(d.planResult.data.plan.analysis[tool],null);
        assert.deepEqual(d,before);assert.equal(m.formalApprovalEnabled,false);assert.equal(m.authorizationConfirmed,false);
    });

    test(tool+' truly unrun with frozen risk remains a valid incomplete display, never authorization',()=>{
        const {d,field}=declareAnalysisNotRun(tool,true),before=structuredClone(d),m=view.inspect(d),html=view.render(d);
        assert.equal(d.snapshot.results.some(result=>result.tool===tool),false);
        assert.deepEqual(m.errors,[]);assert.deepEqual(m.reportSources[field],[]);
        assert.equal(m.packageSucceeded,true);assert.equal(m.boundOperations.length,4);
        assert.equal(m.hasRisks,true);assert.equal(m.authorizationConfirmed,false);assert.equal(m.formalApprovalEnabled,false);
        assert.match(html,/analysis_not_run/);assert.ok(html.includes(tool+' explicitly not run'));
        assert.match(html,/打包执行成功，但材料包仍有缺项或未决事项/);assert.match(html,/不确认服务端审批/);
        assert.equal(view.inspectSnapshot(d.snapshot).state,'provided');assert.deepEqual(d,before);
    });
}

test('recorded empty, failed or malformed analysis also cannot be relabeled as unrun',()=>{
    for(const tool of ['compare_versions','detect_conflicts'])for(const kind of ['empty','failed','malformed']){
        const {d,index,field}=declareAnalysisNotRun(tool,false),key=tool==='compare_versions'?'groups':'conflicts';
        if(kind==='empty')d.snapshot.results[index].data[key]=[];
        if(kind==='failed')Object.assign(d.snapshot.results[index],{success:false,data:null,error:'synthetic analysis failure'});
        if(kind==='malformed')d.snapshot.results[index]={tool,success:true,data:null,message:'malformed',error:null};
        const m=view.inspect(d);
        assert.match(m.errors.join(),/分析来源矛盾/);assert.equal(m.reportSources[field],null);assert.equal(m.packageSucceeded,false);
        assert.notEqual(view.inspectSnapshot(d.snapshot).state,'provided');
    }
});
