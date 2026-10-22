const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const base = path.resolve(__dirname,'..');

function harness(mode='real') {
    const elements=new Map(), timers=new Map(), calls=[]; let timerId=0;
    const el=id=>{
        if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',replaceChildren(){this.innerHTML='';},hidden:false,disabled:false,dataset:{},style:{},listeners:{},classList:{add(){},remove(){},toggle(){}},addEventListener(k,v){this.listeners[k]=v;},setAttribute(k,v){this[k]=v;},querySelectorAll(){return[];},appendChild(){},remove(){}});
        return elements.get(id);
    };
    const c={window:{},console,AbortController,document:{getElementById:el,querySelectorAll:()=>[],createElement:()=>el('toast')},navigator:{clipboard:{writeText:async()=>{}}},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),setInterval(){throw Error('Unexpected interval');},clearInterval(){},fetch:async(url,options)=>{if(!url.startsWith('/api/agent/'))return {ok:false};calls.push({url,options});return c.respond(url,options);}};
    vm.createContext(c);
    for(const file of ['agent-api.js','agent-clarification.js','agent-mock.js','agent-results.js','package-preview.js','organization-preview.js','organization-demo.js','agent-flow-visualization.js'])vm.runInContext(fs.readFileSync(path.join(base,file),'utf8'),c);
    c.AgentClarification=c.window.AgentClarification;c.AgentAPI=c.window.AgentAPI;c.AgentMock=c.window.AgentMock;c.AgentResults=c.window.AgentResults;c.AgentFlowVisualization=c.window.AgentFlowVisualization;
    c.OrganizationPreview=c.window.OrganizationPreview;c.OrganizationDemo=c.window.OrganizationDemo;
    c.PackagePreview=c.window.PackagePreview;
    vm.runInContext(fs.readFileSync(path.join(base,'index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1],c);
    vm.runInContext('window.state=agentState',c);
    el('agentMode').value=mode;c.window.state.mode=mode;c.AgentAPI.setMode(mode);el('agentScenario').value='happy';el('agentWorkspacePath').value='E:/unknown-workspace';el('agentGoal').value='准备课程材料';
    return {c,el,state:c.window.state,calls,timers};
}
const response=(data,status=200)=>({ok:status<300,status,text:async()=>JSON.stringify(data)});
const snapshot=(status,extra={})=>({task:{task_id:'task',status},plan:{steps:[]},results:[],pending_operations:[],preview_id:null,error:null,...extra});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
function seedTask(h,status='completed'){
    h.state.mode='real';h.c.AgentAPI.setMode('real');h.c.renderAgent(snapshot(status,{preview_id:'preview'}));
}
function replaceTask(h,{sameId=false,advanceGeneration=true}={}){
    if(advanceGeneration)h.state.generation++;
    h.state.task={task_id:sameId?'task':'new-task',status:'planning'};
    h.state.snapshot={task:h.state.task};h.state.report=null;h.state.busy=true;
    h.state.pollInFlight=true;h.state.decisionBusy=true;h.state.decisionAction='new-request';h.state.userRejected=false;
    h.el('agentFinal').textContent='new task view';h.el('agentErrorDetail').textContent='new task error';
    h.el('agentFinalCard').dataset.completed='false';
}
function assertReplacementUntouched(h){
    assert.equal(h.state.task.status,'planning');assert.equal(h.state.report,null);
    assert.equal(h.state.pollInFlight,true);assert.equal(h.state.decisionBusy,true);
    assert.equal(h.state.decisionAction,'new-request');assert.equal(h.state.userRejected,false);
    assert.equal(h.el('agentFinal').textContent,'new task view');
    assert.equal(h.el('agentErrorDetail').textContent,'new task error');assert.equal(h.el('agentFinalCard').dataset.completed,'false');
}

test('real polling handles every task state, exact preview, report and single loop',async()=>{
    const h=harness();let status='created';
    h.c.respond=(url,options)=>{
        if(url==='/api/agent/tasks'){assert.deepEqual(JSON.parse(options.body),{user_goal:'准备课程材料',workspace:'E:/unknown-workspace'});return response({task_id:'task',status},202);}
        if(url.endsWith('/approve')){assert.deepEqual(JSON.parse(options.body),{preview_id:'exact-preview'});status='executing';return response(snapshot(status));}
        if(url.endsWith('/report'))return response({task_id:'task',status:'completed',missing_items:[],conflicts:[],package_path:''});
        return response(snapshot(status,status==='awaiting_approval'?{preview_id:'exact-preview'}:{}));
    };
    await Promise.all([h.c.runAgent(),h.c.runAgent()]);assert.equal(h.calls.length,1);
    for(const next of ['created','planning','executing','verifying']){status=next;await h.c.pollAgent();assert.equal([...h.timers.values()].filter(t=>t.ms===1000).length,1);}
    status='awaiting_approval';await h.c.pollAgent();assert.equal([...h.timers.values()].filter(t=>t.ms===1000).length,0);
    await Promise.all([h.c.decideAgent(true),h.c.decideAgent(true)]);assert.equal(h.calls.filter(r=>r.url.endsWith('/approve')).length,1);
    status='completed';await h.c.pollAgent();assert.match(h.el('agentFinal').innerHTML,/缺项数组为空不代表/);
    status='failed';h.c.respond=()=>response(snapshot(status,{error:'Document read failed'}));await h.c.pollAgent();
    assert.equal(h.state.report,null);assert.equal(h.el('copyPackagePath').hidden,true);assert.equal(h.el('agentFinalCard').dataset.completed,'false');
    assert.throws(()=>h.c.renderAgentReport({task_id:'task',status:'completed'}),/Invalid FinalReport/);
    assert.equal(h.calls.filter(r=>r.url.endsWith('/report')).length,1);
});
test('409 only refreshes preview once and never automatically retries approval',async()=>{
    const h=harness();let refreshed=false;
    h.c.respond=url=>url==='/api/agent/tasks'?response({task_id:'task',status:'created'},202):url.endsWith('/approve')?(refreshed=true,response({detail:'stale'},409)):response(snapshot('awaiting_approval',{preview_id:refreshed?'new':'old'}));
    await h.c.runAgent();await h.c.pollAgent();await h.c.decideAgent(true);
    assert.equal(h.calls.filter(r=>r.url.endsWith('/approve')).length,1);assert.equal(h.state.snapshot.preview_id,'new');
    assert.match(h.el('agentErrorDetail').textContent,/preview is no longer current/);
});
test('snapshot errors in nonfailed states remain visible; real network failure never falls back',async()=>{
    const h=harness();h.c.respond=url=>url==='/api/agent/tasks'?response({task_id:'task',status:'created'},202):response(snapshot('planning',{error:'需要检查输入来源'}));
    await h.c.runAgent();await h.c.pollAgent();assert.equal(h.el('agentErrorDetail').textContent,'需要检查输入来源');
    const unavailable=harness();unavailable.c.respond=()=>{throw Error('network');};
    unavailable.c.AgentMock.createTask=()=>{throw Error('Unexpected Mock fallback');};
    await unavailable.c.runAgent();assert.match(unavailable.el('agentErrorDetail').textContent,/backend unavailable/);assert.equal(unavailable.state.mode,'real');
});
test('failed task never requests report; report 409 is not reported as success',async()=>{
    const h=harness();h.c.respond=url=>url==='/api/agent/tasks'?response({task_id:'task',status:'created'},202):response(snapshot('failed',{error:'Tool failed'}));
    await h.c.runAgent();await h.c.pollAgent();assert.equal(h.calls.some(r=>r.url.endsWith('/report')),false);
    const pending=harness();pending.c.respond=url=>url==='/api/agent/tasks'?response({task_id:'task',status:'created'},202):url.endsWith('/report')?response({detail:'not ready'},409):response(snapshot('completed'));
    await pending.c.runAgent();await pending.c.pollAgent();assert.match(pending.el('agentFinal').textContent,/尚未生成/);assert.equal(pending.state.report,null);
});
test('Mock happy, reject and failure flows stay separate and functional',async()=>{
    for(const scenario of ['happy','reject','failed']){
        const h=harness('mock');h.el('agentScenario').value=scenario==='failed'?'failed':'happy';
        await h.c.runAgent();for(let i=0;i<5&&h.state.task.status!=='failed';i++)await h.c.pollAgent();
        if(scenario==='failed'){assert.equal(h.state.task.status,'failed');continue;}
        assert.equal(h.state.task.status,'awaiting_approval');await h.c.decideAgent(scenario==='happy');
        if(scenario==='reject')assert.equal(h.state.task.status,'failed');
        else{for(let i=0;i<3;i++)await h.c.pollAgent();assert.equal(h.state.task.status,'completed');assert.ok(h.state.report);}
        assert.equal(h.calls.length,0);
    }
});
test('Real Mode creates and polls a real Agent task; the graph follows returned snapshots',async()=>{
    const h=harness('real');h.el('agentScenario').value='happy';
    const tools=['list_files','search_files','read_document','compare_versions','detect_conflicts','extract_requirements','create_folder','verify_result'];
    const makeSteps=statuses=>tools.map((tool,i)=>({step_id:'step_'+i,tool,description:'步骤 '+tool,status:statuses[i],risk:'low'}));
    const planning={task:{task_id:'task',status:'planning',user_goal:'准备课程材料',workspace:'E:/unknown-workspace'},plan:{task_id:'task',steps:makeSteps(['completed','running','pending','pending','pending','pending','pending','pending','pending'])},results:[{tool:'list_files',success:true,data:{files:[]},message:'scan',error:null}],pending_operations:[],operations:[],preview_id:null,error:null};
    const completed={task:{task_id:'task',status:'completed',user_goal:'准备课程材料',workspace:'E:/unknown-workspace'},plan:{task_id:'task',steps:makeSteps(tools.map(()=> 'completed'))},results:tools.map(tool=>({tool,success:true,data:tool==='verify_result'?{passed:true}:{},message:'test',error:null})),pending_operations:[],operations:[],preview_id:null,error:null};
    h.c.AgentMock.createTask=()=>{throw Error('Real Mode must not call AgentMock');};
    h.c.AgentMock.getTask=()=>{throw Error('Real Mode must not call AgentMock');};
    h.c.respond=(url,options={})=>{
        if(url==='/api/agent/tasks'&&options.method==='POST')return response({task_id:'task',status:'created',user_goal:'准备课程材料',workspace:'E:/unknown-workspace'},202);
        if(url==='/api/agent/tasks/task/report')return response({task_id:'task',status:'completed',found_files:[],version_groups:[],conflicts:[],missing_items:[],operations:[],package_path:'',summary:'任务完成，结果以实际执行证据为准。'});
        if(url==='/api/agent/tasks/task')return response(completed);
        throw Error('Unexpected Agent endpoint '+url);
    };
    await h.c.runAgent();
    assert.equal(h.state.mode,'real');
    assert.equal(h.calls.length,1);
    assert.equal(h.calls[0].url,'/api/agent/tasks');
    assert.equal(h.calls[0].options.method,'POST');
    h.c.respond=(url,options={})=>{
        if(url==='/api/agent/tasks/task')return response(planning);
        if(url==='/api/agent/tasks/task/report')return response({task_id:'task',status:'completed',found_files:[],version_groups:[],conflicts:[],missing_items:[],operations:[],package_path:'',summary:'任务完成。'});
        throw Error('Unexpected Agent endpoint '+url);
    };
    await h.c.pollAgent();
    assert.equal(h.state.snapshot.task.status,'planning');
    assert.match(h.el('agentFlowVisualization').innerHTML,/data-stage="scan"[^>]*data-status="completed"/);
    assert.match(h.el('agentFlowVisualization').innerHTML,/data-stage="identify"[^>]*data-status="running"/);
    h.c.respond=(url,options={})=>{
        if(url==='/api/agent/tasks/task')return response(completed);
        if(url==='/api/agent/tasks/task/report')return response({task_id:'task',status:'completed',found_files:[],version_groups:[],conflicts:[],missing_items:[],operations:[],package_path:'',summary:'任务完成。'});
        throw Error('Unexpected Agent endpoint '+url);
    };
    await h.c.pollAgent();
    assert.equal(h.state.snapshot.task.status,'completed');
    assert.equal(h.state.mode,'real');
    assert.equal(h.state.report.task_id,'task');
    assert.ok(h.calls.some(call=>call.url==='/api/agent/tasks/task'));
    assert.ok(h.calls.some(call=>call.url==='/api/agent/tasks/task/report'));
    assert.match(h.el('agentTaskStatus').textContent,/completed · Real Mode/);
    assert.match(h.el('agentFlowVisualization').innerHTML,/Real Mode · 实时任务状态/);
    assert.match(h.el('agentFlowVisualization').innerHTML,/data-stage="result"[^>]*data-status="completed"/);
    assert.doesNotMatch(h.el('agentFlowVisualization').innerHTML,/前端演示|仅前端|不调用真实模型/);
    assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/前端演示|仅前端|不调用真实模型/);
    assert.equal(h.state.presentationDemo,undefined);
});
test('every organization preview sends no requests and material Mock happy path still completes',async()=>{
    const h=harness();h.c.switchAgentWorkflow('organization');assert.equal(h.el('organizationWorkspace').hidden,false);assert.equal(h.el('materialWorkspace').hidden,true);
    h.c.setOrganizationDemo(true);
    for(const scenario of ['mixed','single','empty','unknown','collision','incomplete']){
        h.el('organizationScenario').value=scenario;h.c.showOrganizationPreview();assert.match(h.el('organizationPreview').innerHTML,scenario==='incomplete'?/结构不完整/:/本地 UI 演示预览/);
    }
    h.c.showOrganizationPreview(true);assert.match(h.el('organizationPreview').innerHTML,/尚未开始/);
    h.c.switchAgentWorkflow('materials');assert.equal(h.el('materialWorkspace').hidden,false);assert.equal(h.calls.length,0);
    h.el('agentMode').value='mock';await h.c.runAgent();for(let i=0;i<5;i++)await h.c.pollAgent();
    assert.equal(h.state.task.status,'awaiting_approval');await h.c.decideAgent(true);for(let i=0;i<3;i++)await h.c.pollAgent();
    assert.equal(h.state.task.status,'completed');assert.equal(h.calls.length,0);
});

test('formal organization reuses input, blocks all Agent actions and never promotes Fixture or Package data',async()=>{
    const h=harness(),workspace=h.el('agentWorkspacePath').value,goal=h.el('agentGoal').value;
    h.c.switchAgentWorkflow('organization');
    assert.equal(h.state.workflow,'organization');assert.equal(h.state.organizationDemo,false);
    assert.equal(h.el('agentWorkspacePath').value,workspace);assert.equal(h.el('agentGoal').value,goal);
    assert.match(h.el('organizationRealPreview').innerHTML,/分类接口待团队确认/);
    assert.equal(h.el('organizationDemoPanel').hidden,true);
    for(const id of ['runAgent','refreshAgent','approveAgent','rejectAgent','organizationScan','organizationExecute'])assert.equal(h.el(id).disabled,true,id);
    h.el('organizationScenario').value='mixed';h.c.showOrganizationPreview();
    assert.doesNotMatch(h.el('organizationRealPreview').innerHTML,/本地UI样本|结题报告|摘录.docx/);
    for(const mode of ['real','mock']){
        h.el('agentMode').value=mode;await h.c.runAgent();await h.c.pollAgent();await h.c.decideAgent(true);await h.c.decideAgent(false);
    }
    assert.equal(h.calls.length,0);assert.equal(h.state.task,null);
    const html=h.el('organizationRealPreview').innerHTML;
    h.c.renderAgent(require('../package-fixtures.js').get('success').snapshot);
    h.c.renderAgentReport({status:'completed',task_id:'old',package_path:'PRIVATE_PATH'});
    assert.equal(h.el('organizationRealPreview').innerHTML,html);assert.equal(h.state.report,null);
    h.c.setOrganizationDemo(true);h.c.showOrganizationPreview();assert.match(h.el('organizationPreview').innerHTML,/本地 UI 演示预览/);
    h.c.setOrganizationDemo(false);assert.match(h.el('organizationRealPreview').innerHTML,/真实分类数据尚未接入/);
    h.c.switchAgentWorkflow('materials');assert.equal(h.state.task,null);assert.equal(h.state.approvalValid,false);
    assert.equal(h.el('organizationRealPreview').textContent,'');assert.equal(h.calls.length,0);
});

test('workflow generation prevents late snapshots and reports from entering organization or a fresh material view',async()=>{
    const h=harness();seedTask(h);const context=h.c.agentRequestContext();
    const old=snapshot('completed',{results:[{tool:'plan_package',success:true,data:{plan:{path:'PRIVATE_OLD_MAPPING'}},message:'old',error:null}]});
    h.c.switchAgentWorkflow('organization');const formal=h.el('organizationRealPreview').innerHTML;
    assert.equal(h.c.isCurrentAgentRequest(context),false);
    await h.c.applyAgentSnapshot(old,context);
    assert.equal(h.state.task,null);assert.equal(h.el('organizationRealPreview').innerHTML,formal);assert.equal(h.calls.length,0);
    h.c.switchAgentWorkflow('materials');await h.c.applyAgentSnapshot(old,context);
    assert.equal(h.state.snapshot,null);assert.equal(h.state.report,null);assert.equal(h.calls.length,0);
    assert.doesNotMatch(h.el('agentPackagePreview').textContent,/PRIVATE_OLD_MAPPING/);
});

test('Real Snapshot retains matching ToolResults and renders them separately from extraction',async()=>{
    const h=harness();const candidates=[{file_id:'file_second',filename:'表_v2.txt',path:'E:\\unknown\\表_v2.txt'},{file_id:'file_first',filename:'表.txt',path:'E:\\unknown\\表.txt'}];
    const matching={tool:'match_requirements',success:true,data:{required_documents:['表','证明'],matched:[{requirement:'表',documents:candidates}],missing:['证明']},message:'matched',error:null};
    let results=[matching,{tool:'extract_requirements',success:true,data:{required_documents:['只提取到的要求']}}];
    h.c.respond=url=>url==='/api/agent/tasks'?response({task_id:'task',status:'created'},202):url.endsWith('/report')?response({task_id:'task',status:'completed',missing_items:['证明'],package_path:''}):response(snapshot('completed',{results}));
    await h.c.runAgent();await h.c.pollAgent();
    assert.equal(JSON.stringify(h.state.snapshot.results[0]),JSON.stringify(matching));
    assert.match(h.el('agentMaterials').innerHTML,/只提取到的要求/);assert.doesNotMatch(h.el('agentMaterials').innerHTML,/file_second/);
    for(const target of ['agentMatching','agentFinal']){
        const html=h.el(target).innerHTML;assert.match(html,/file_second/);assert.match(html,/file_first/);assert.ok(html.indexOf('file_second')<html.indexOf('file_first'));
        assert.match(html,/本次未找到文件名候选/);assert.doesNotMatch(html,/匹配尚未接入/);
    }
    assert.match(h.el('agentFinal').innerHTML,/未生成材料包/);assert.equal(h.el('copyPackagePath').hidden,true);
    results=[matching,{tool:'match_requirements',success:false,data:null,error:'matching failed'}];
    h.c.respond=()=>response(snapshot('failed',{results,error:'matching failed'}));await h.c.pollAgent();
    assert.match(h.el('agentMatching').innerHTML,/matching failed/);assert.doesNotMatch(h.el('agentMatching').innerHTML,/file_second/);assert.equal(h.state.report,null);
    assert.equal(h.calls.filter(r=>r.url.endsWith('/report')).length,1);
});

test('approval displays exact backend arguments and failure details without promoting partial operations',async()=>{
    const h=harness(), operation={step_id:'copy',tool:'copy_file',risk:'medium',status:'awaiting_approval',description:'copy candidate',arguments:{source:'E:\\in\\candidate.txt',destination:'E:\\out\\candidate.txt'}};
    h.c.respond=url=>url==='/api/agent/tasks'?response({task_id:'task',status:'created'},202):response(snapshot('awaiting_approval',{pending_operations:[operation],preview_id:'frozen-preview'}));
    await h.c.runAgent();await h.c.pollAgent();for(const value of [operation.arguments.source,operation.arguments.destination,'copy_file','frozen-preview'])assert.ok(h.el('agentActions').innerHTML.includes(value.replaceAll('\\','\\\\'))||h.el('agentActions').innerHTML.includes(value));
    h.c.respond=()=>response(snapshot('failed',{results:[{tool:'copy_file',success:true,data:{},message:'one copy completed'},{tool:'copy_file',success:false,data:null,error:'verification failed'}],error:'verification failed; one copy may already exist'}));
    await h.c.pollAgent();assert.match(h.el('agentErrorDetail').textContent,/verification failed; one copy may already exist/);
    assert.match(h.el('agentOtherResults').innerHTML,/one copy completed/);assert.match(h.el('agentOtherResults').innerHTML,/verification failed/);
    assert.equal(h.state.report,null);assert.equal(h.calls.some(c=>c.url.endsWith('/report')),false);
});

test('late report success and errors cannot change a new generation, even with the same task id',async()=>{
    for(const replacement of [{sameId:false},{sameId:true},{advanceGeneration:false}])for(const fails of [false,true]){
        const h=harness(),request=deferred(),started=deferred();seedTask(h);
        h.c.AgentAPI.getReport=()=>{started.resolve();return request.promise;};
        const pending=h.c.applyAgentSnapshot(snapshot('completed'));await started.promise;
        replaceTask(h,replacement);
        if(fails)request.reject(Error('old report error'));else request.resolve({task_id:'task',status:'completed',package_path:''});
        await pending;assertReplacementUntouched(h);
    }
});

test('a newer failed snapshot prevents a late successful report for the same task',async()=>{
    const h=harness(),request=deferred();seedTask(h);h.c.AgentAPI.getReport=()=>request.promise;
    const pending=h.c.applyAgentSnapshot(snapshot('completed'));
    await h.c.applyAgentSnapshot(snapshot('failed',{error:'current failure'}));
    request.resolve({task_id:'task',status:'completed',package_path:''});await pending;
    assert.equal(h.state.task.status,'failed');assert.equal(h.state.report,null);
    assert.equal(h.el('agentErrorDetail').textContent,'current failure');assert.equal(h.el('agentFinalCard').dataset.completed,'false');
});

test('late approve and reject responses and errors never alter another task or release its locks',async()=>{
    for(const approve of [true,false])for(const fails of [false,true]){
        const h=harness(),request=deferred();seedTask(h,'awaiting_approval');
        h.c.AgentAPI[approve?'approveTask':'rejectTask']=()=>request.promise;
        const pending=h.c.decideAgent(approve);replaceTask(h);
        if(fails)request.reject(Object.assign(Error('old conflict'),{status:409}));else request.resolve(snapshot(approve?'executing':'failed'));
        await pending;assertReplacementUntouched(h);assert.equal(h.calls.length,0);
    }
});

test('409 refresh is bound to its original task and ignores late refresh results and failures',async()=>{
    for(const fails of [false,true]){
        const h=harness(),refresh=deferred(),started=deferred();seedTask(h,'awaiting_approval');
        h.c.AgentAPI.approveTask=async()=>{throw Object.assign(Error('stale'),{status:409});};
        h.c.AgentAPI.getTask=id=>{assert.equal(id,'task');started.resolve();return refresh.promise;};
        const pending=h.c.decideAgent(true);await started.promise;replaceTask(h);
        if(fails)refresh.reject(Error('old refresh failed'));else refresh.resolve(snapshot('awaiting_approval',{preview_id:'old-new-preview'}));
        await pending;assertReplacementUntouched(h);
    }
});

test('old polling success or error cannot stop new task polling or clear new request state',async()=>{
    for(const fails of [false,true]){
        const h=harness(),request=deferred();seedTask(h,'planning');h.c.AgentAPI.getTask=()=>request.promise;
        const pending=h.c.pollAgent();replaceTask(h);
        const timer=h.c.setTimeout(()=>{},1000);
        if(fails)request.reject(Error('old polling error'));else request.resolve(snapshot('completed'));
        await pending;assertReplacementUntouched(h);assert.equal(h.timers.has(timer),true);
    }
});

test('a wrong-task approval response cannot mark the current task as rejected',async()=>{
    const h=harness();seedTask(h,'awaiting_approval');
    h.c.AgentAPI.rejectTask=async()=>snapshot('failed',{task:{task_id:'wrong-task',status:'failed'}});
    await h.c.decideAgent(false);
    assert.equal(h.state.task.task_id,'task');assert.equal(h.state.task.status,'awaiting_approval');
    assert.equal(h.state.userRejected,false);assert.match(h.el('agentErrorDetail').textContent,/does not match/);
});

test('malformed Package approval and success stay blocked, rejection remains available',async()=>{
    const h=harness();seedTask(h,'awaiting_approval');
    h.c.renderAgent(snapshot('awaiting_approval',{preview_id:'package-preview',results:[{tool:'plan_package',success:true,data:{},message:'plan only',error:null}]}));
    assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.el('rejectAgent').disabled,false);
    assert.match(h.el('agentActions').innerHTML,/后端负责校验授权/);
    await h.c.decideAgent(true);assert.equal(h.calls.length,0);assert.match(h.el('agentErrorDetail').textContent,/不会发送批准请求/);
    h.c.AgentAPI.rejectTask=async(id,preview)=>{assert.equal(id,'task');assert.equal(preview,'package-preview');return snapshot('failed',{error:'Rejected'});};
    await h.c.decideAgent(false);assert.equal(h.state.task.status,'failed');assert.equal(h.state.userRejected,true);
    seedTask(h);h.c.renderAgentReport({task_id:'task',status:'completed',package_path:'E:/package'});assert.match(h.el('agentFinal').innerHTML,/无法验证成功/);
    assert.equal(h.state.report,null);
});

// Synthetic HTTP responses exercise the production page, not a live backend/LLM acceptance.
function packageHttpSnapshot(){
    const s=require('../package-fixtures.js').get('complete').snapshot;
    s.task.task_id='task';s.results[4].data.plan.task.task_id='task';
    s.preview_id='server-preview';s.pending_operations=[{step_id:'package_build',tool:'build_package',risk:'medium',status:'pending',arguments:{},description:'server preview'}];
    return s;
}
test('production page renders Snapshot Package data without loading Fixture code or issuing extra requests',async()=>{
    const h=harness(),s=packageHttpSnapshot();
    h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):response(s);
    await h.c.runAgent();await h.c.pollAgent();
    const html=h.el('agentPackagePreview').innerHTML;
    for(const label of ['真实 TaskSnapshot 只读展示','server-preview','结题报告.txt','plan_sha256','选择依据','缺项与风险'])assert.ok(html.includes(label),label);
    assert.equal(h.c.window.PackageFixtures,undefined);assert.equal(h.c.window.PackageDemo,undefined);
    assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.el('rejectAgent').disabled,false);
    assert.equal(h.calls.length,2);await h.c.decideAgent(true);assert.equal(h.calls.length,2);
    assert.deepEqual(JSON.parse(JSON.stringify(h.state.snapshot)),s);
});
test('production page distinguishes unavailable planning, malformed manifests and current failures',async()=>{
    const h=harness();let s=packageHttpSnapshot();
    h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):response(s);
    await h.c.runAgent();await h.c.pollAgent();
    delete s.results[4].data.plan.selected_files;await h.c.pollAgent();
    assert.match(h.el('agentPackagePreview').innerHTML,/数据不完整/);
    s=packageHttpSnapshot();s.results=[];await h.c.pollAgent();
    assert.match(h.el('agentPackagePreview').innerHTML,/真实 Package 规划数据尚未提供/);
    assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/提议文件 1/);
    s=packageHttpSnapshot();s.results.push({tool:'plan_package',success:false,data:null,message:'failed',error:'current plan failed'});s.task.status='failed';
    await h.c.pollAgent();assert.match(h.el('agentPackagePreview').innerHTML,/current plan failed/);
    assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/具体文件映射/);assert.equal(h.state.report,null);
});
test('production Package preview rejects stale evidence and task context pollution',async()=>{
    for(const field of ['task_id','user_goal','workspace']){
        const h=harness(),s=packageHttpSnapshot();
        h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):response(s);
        await h.c.runAgent();
        s.results[4].data.plan.task[field]='FOREIGN';await h.c.pollAgent();
        assert.match(h.el('agentPackagePreview').innerHTML,/归属不一致/);assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/结题报告.txt/);
    }
    const h=harness(),s=packageHttpSnapshot();
    h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):response(s);
    await h.c.runAgent();s.task.workspace='FOREIGN';s.results[4].data.plan.task.workspace='FOREIGN';await h.c.pollAgent();
    assert.match(h.el('agentPackagePreview').innerHTML,/当前任务归属不一致/);
    s.task.workspace=h.state.taskContext.workspace;s.results[4].data.plan.task.workspace=s.task.workspace;
    s.results.push({...s.results[3]});await h.c.pollAgent();assert.match(h.el('agentPackagePreview').innerHTML,/过期/);
    assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/具体文件映射/);
});

test('malformed current Package ToolResult cannot interrupt task rendering or enable approval',async()=>{
    const changes=[
        ...[null,[], 'bad',42,true].map(value=>r=>r.data=value),
        r=>delete r.data,r=>r.data={},r=>delete r.data.plan,
        ...[null,[], 'bad',42].map(value=>r=>r.data.plan=value),
        ...[null,[],{},42,'bad'].map(value=>r=>r.data.plan_sha256=value),
        r=>delete r.data.plan_sha256,r=>r.data.plan.plan_id=null,r=>r.data.plan.task=null
    ];
    for(const change of changes){
        const h=harness(),s=packageHttpSnapshot(),latest=structuredClone(s.results[4]);change(latest);s.results.push(latest);
        const before=structuredClone(s);
        h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):response(s);
        await h.c.runAgent();await assert.doesNotReject(()=>h.c.pollAgent());
        assert.equal(h.state.task.status,'awaiting_approval');assert.equal(h.state.pollInFlight,false);
        assert.match(h.el('agentTaskStatus').textContent,/awaiting_approval.*Real Mode/);
        assert.match(h.el('agentPackagePreview').innerHTML,/格式异常|归属不一致|不是对象/);
        assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/结题报告.txt|具体文件映射|文件验证：通过/);
        assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.el('rejectAgent').disabled,false);
        assert.match(h.el('agentActions').innerHTML,/关联无效/);assert.doesNotMatch(h.el('agentActions').innerHTML,/server preview/);
        assert.equal(h.calls.length,2);await h.c.decideAgent(true);assert.equal(h.calls.length,2);
        assert.equal(h.state.report,null);assert.deepEqual(s,before);
    }
});

test('renderAgent clears valid Package mappings for invalid, failed and unavailable snapshots',async()=>{
    const cases=[
        ['invalid',s=>delete s.results[4].data.plan.selected_files[0].snapshot,/快照数据不完整/],
        ['invalid',s=>s.results.splice(4,0,structuredClone(s.results[3])),/来源不一致或已过期/],
        ['failed',s=>{s.task.status='failed';s.error='current task failed';},/当前失败/],
        ['unavailable',s=>{s.results=[];},/规划数据尚未提供/]
    ];
    for(const [state,change,warning] of cases){
        const h=harness(),s=packageHttpSnapshot(),file=structuredClone(s.results[4].data.plan.selected_files[0]);
        h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):response(s);
        await h.c.runAgent();await h.c.pollAgent();
        assert.match(h.el('agentPackagePreview').innerHTML,/结题报告.txt/);
        change(s);const before=structuredClone(s);
        h.el('agentTaskStatus').textContent='waiting for the next rendered snapshot';
        await assert.doesNotReject(()=>h.c.pollAgent());
        const html=h.el('agentPackagePreview').innerHTML;
        assert.match(html,warning);for(const value of ['提议文件','具体文件映射',file.source.filename,file.source.path,file.target])assert.equal(html.includes(value),false,value);
        assert.equal(h.state.task.status,s.task.status);assert.ok(h.el('agentTaskStatus').textContent.startsWith(s.task.status+' · Real Mode'));
        assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.state.pollInFlight,false);assert.equal(h.state.report,null);
        assert.equal(h.calls.length,3);await h.c.decideAgent(true);assert.equal(h.calls.length,3);
        assert.deepEqual(s,before);assert.equal(h.c.PackagePreview.inspectSnapshot(h.state.snapshot,h.state.taskContext).state,state);
    }
});

test('production Package progress and new failed verification preserve the Snapshot detail gate after integration',async()=>{
    const fixtures=require('../package-fixtures.js');
    for(const name of ['executing','verifying','new_verification','failed_copy']){
        const d=fixtures.get(name==='new_verification'?'success':name==='failed_copy'?'partial':name),s=d.snapshot;
        if(name==='new_verification'){
            const bad=structuredClone(s.results[8]);bad.data.passed=false;bad.data.checks[0].passed=false;
            s.results.splice(9,0,bad);s.package_execution.final_result_index=10;
        }
        const before=structuredClone(s),h=harness();
        h.c.respond=url=>url==='/api/agent/tasks'?response({...s.task,status:'created'},202):url.endsWith('/report')?response({detail:'Package report unavailable'},409):response(s);
        await h.c.runAgent();await assert.doesNotReject(()=>h.c.pollAgent());
        const html=h.el('agentPackagePreview').innerHTML;
        if(['executing','verifying'].includes(name)){
            assert.match(html,/Package 执行中/);assert.match(html,/结题报告.txt/);
            assert.equal(h.c.PackagePreview.inspectSnapshot(h.state.snapshot,h.state.taskContext).state,'provided');
        }else{
            assert.doesNotMatch(html,/具体文件映射|结题报告.txt|文件验证：通过|文件操作执行成功/);
            assert.match(html,name==='new_verification'?/验证记录缺失、重复或关联不完整/:/当前失败/);
        }
        assert.ok(h.el('agentTaskStatus').textContent.startsWith(s.task.status));
        assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.state.report,null);
        const count=h.calls.length;await h.c.decideAgent(true);assert.equal(h.calls.length,count);
        assert.equal(h.calls.filter(call=>call.url.endsWith('/approve')).length,0);
        assert.equal(h.c.window.PackageFixtures,undefined);assert.deepEqual(s,before);
    }
});

// This is synthetic contract-shaped HTTP coverage, not Windows acceptance.
function boundPackage(h,scenario='complete') {
    const d=require('../package-fixtures.js').get(scenario),s=d.snapshot,p=s.results[4].data.plan;
    s.task.status='awaiting_approval'; s.task.task_id='task';p.task.task_id='task';
    s.package_execution=null; s.results=s.results.slice(0,5); s.preview_id='sha256:'+'e'.repeat(64);
    s.pending_operations=p.operations.map(o=>({step_id:o.step_id,tool:({create_directory:'create_folder',copy:'copy_file',write_report:'write_package_report',verify:'verify_result'})[o.kind],risk:o.kind==='verify'?'low':'medium',status:'awaiting_approval',arguments:o.kind==='create_directory'?{path:p.destination}:o.kind==='copy'?{source:p.selected_files[o.selected_file_index].source.path,destination:p.selected_files[o.selected_file_index].target}:o.kind==='write_report'?{task_id:'task',plan_id:p.plan_id,plan_sha256:d.planResult.data.plan_sha256}:{task_id:'task',workspace:p.task.workspace,expected:p.verification_targets}}));
    h.state.mode='real';h.c.AgentAPI.setMode('real');const current=h.c.AgentAPI.parseJSON(JSON.stringify(s));h.state.taskContext={...current.task};h.c.renderAgent(current);assert.equal(h.c.PackagePreview.approval(current,h.state.taskContext).ready,true,JSON.stringify(h.c.PackagePreview.approval(current,h.state.taskContext).issues));
    return {s:current,p:current.results[4].data.plan,d};
}
test('real Package uses exact server preview and same-preview risk acceptance, with duplicate protection',async()=>{
    const h=harness(),{s}=boundPackage(h,'risks');
    assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.el('packageRiskControl').hidden,false);
    await h.c.decideAgent(true);assert.equal(h.calls.length,0);
    h.el('packageRiskIntent').checked=true;h.c.confirmPackageRisk();assert.equal(h.el('approveAgent').disabled,false);
    const pending=deferred();h.c.respond=(url,options)=>{assert.ok(url.endsWith('/approve'));assert.deepEqual(JSON.parse(options.body),{preview_id:s.preview_id,accept_incomplete:true});return pending.promise;};
    const first=h.c.decideAgent(true);await h.c.decideAgent(true);assert.equal(h.calls.length,1);assert.equal(h.el('approveAgent').disabled,true);
    pending.resolve(response({...s,task:{...s.task,status:'executing'},preview_id:null,pending_operations:[]}));await first;
    assert.equal(h.state.acceptedPackageRisk,null);assert.equal(h.el('approveAgent').disabled,true);
});
test('changed preview, plan, selection or risks invalidate local acceptance; invalid pending cannot approve',async()=>{
    for(const change of [s=>s.preview_id='sha256:'+'f'.repeat(64),s=>s.results[4].data.plan.plan_id='package_plan_'+'2'.repeat(32),s=>s.results[4].data.plan.selected_files[0].reason='changed reason',s=>s.results[4].data.plan.missing.push('extra gap')]){
        const h=harness(),{s}=boundPackage(h,'risks');h.el('packageRiskIntent').checked=true;h.c.confirmPackageRisk();change(s);h.c.renderAgent(s);
        assert.equal(h.state.acceptedPackageRisk,null);assert.equal(h.el('packageRiskIntent').checked,false);assert.equal(h.el('approveAgent').disabled,true);
    }
    const h=harness(),{s}=boundPackage(h);s.pending_operations[1].arguments.destination='foreign path';h.c.renderAgent(s);
    await h.c.decideAgent(true);assert.equal(h.calls.length,0);assert.equal(h.el('approveAgent').disabled,true);
});
test('Package rejection never sends accept_incomplete and stale approval clears risk intent',async()=>{
    const h=harness(),{s}=boundPackage(h,'risks');h.el('packageRiskIntent').checked=true;h.c.confirmPackageRisk();
    h.c.respond=(url,options)=>{assert.ok(url.endsWith('/reject'));assert.deepEqual(JSON.parse(options.body),{preview_id:s.preview_id});return response({...s,task:{...s.task,status:'failed'},preview_id:null,error:'User rejected pending operations'});};
    await h.c.decideAgent(false);assert.equal(h.calls.length,1);assert.equal(h.state.userRejected,true);assert.equal(h.state.acceptedPackageRisk,null);
    const stale=harness(),data=boundPackage(stale,'risks');stale.el('packageRiskIntent').checked=true;stale.c.confirmPackageRisk();
    stale.c.respond=url=>url.endsWith('/approve')?response({detail:'stale'},409):response(data.s);
    await stale.c.decideAgent(true);assert.equal(stale.calls.filter(c=>c.url.endsWith('/approve')).length,1);assert.equal(stale.el('packageRiskIntent').checked,false);assert.equal(stale.el('approveAgent').disabled,true);
});
test('lossless transport preserves distinct nanosecond tokens, escaped strings and primitive types',()=>{
    const h=harness(),api=h.c.AgentAPI;
    const parsed=api.parseJSON('{"mtime_ns":1792310400000000001,"second":1792310400000000002,"s":"1792310400000000001","n":null,"x":[true,8,1.5],"__proto__":{"x":1}}');
    assert.equal(parsed.mtime_ns,1792310400000000001n);assert.notEqual(parsed.mtime_ns,parsed.second);assert.equal(typeof parsed.s,'string');assert.equal(parsed.n,null);assert.equal(parsed.x[1],8);assert.equal(parsed.x[2],1.5);assert.equal(Object.hasOwn(parsed,'__proto__'),true);assert.equal({}.x,undefined);
    for(const raw of ['[1,]','{"a":1,}','01','null false','"broken'])assert.throws(()=>api.parseJSON(raw));
    const {s}=boundPackage(h);s.results[4].data.plan.selected_files[0].snapshot.mtime_ns=1792310400000000001n;h.c.renderAgent(s);
    assert.doesNotMatch(h.el('agentPackagePreview').innerHTML,/精度无法确认/);assert.match(h.el('agentPackagePreview').innerHTML,/具体文件映射/);
});
test('current full Package report is rendered only after bound execution and verification; failed report never wins',()=>{
    const h=harness(),d=h.c.AgentAPI.parseJSON(JSON.stringify(require('../package-fixtures.js').get('success')));
    h.state.mode='real';h.state.taskContext={...d.snapshot.task};h.c.renderAgent(d.snapshot);h.c.renderAgentReport(d.report);
    assert.ok(h.state.report);assert.equal(h.el('agentFinalCard').dataset.completed,'true');assert.match(h.el('agentFinal').innerHTML,/不代表材料真实性/);
    h.c.renderAgent({...d.snapshot,task:{...d.snapshot.task,status:'failed'},error:'new failure'});
    assert.throws(()=>h.c.renderAgentReport(d.report),/Invalid FinalReport/);
    const bad=h.c.AgentAPI.parseJSON(JSON.stringify(d));bad.report.found_files=h.c.AgentAPI.parseJSON('[{"path":"foreign"}]');h.state.task=null;h.c.renderAgent(bad.snapshot);h.c.renderAgentReport(bad.report);
    assert.equal(h.state.report,null);assert.equal(h.el('copyPackagePath').hidden,true);assert.match(h.el('agentFinal').innerHTML,/无法验证成功/);
});
test('explicit task restore reads state only and is unavailable to organization workflow',async()=>{
    const h=harness(),d=require('../package-fixtures.js').get('complete');h.el('agentMode').value='real';h.el('agentResumeTask').value=d.snapshot.task.task_id;
    h.c.respond=url=>{assert.ok(!url.endsWith('/approve'));return response(d.snapshot);};await h.c.resumeAgentTask();
    assert.equal(h.calls.length,1);assert.equal(h.calls[0].options.method,'GET');assert.equal(h.state.task.task_id,d.snapshot.task.task_id);
    h.state.busy=false;h.c.switchAgentWorkflow('organization');await h.c.resumeAgentTask();await h.c.decideAgent(true);assert.equal(h.calls.length,1);
});

test('Package without risks uses the unchanged approval payload and invalid flag types are rejected',async()=>{
    const h=harness(),{s}=boundPackage(h);
    s.results[4].data.plan.missing=h.c.AgentAPI.parseJSON('[]');s.results[4].data.plan.unresolved=h.c.AgentAPI.parseJSON('[]');
    // The complete fixture has every analysis slot; no risk is accepted away.
    h.c.renderAgent(s);assert.equal(h.el('approveAgent').disabled,false);
    h.c.respond=(url,options)=>{assert.deepEqual(JSON.parse(options.body),{preview_id:s.preview_id});return response({...s,task:{...s.task,status:'executing'},preview_id:null,pending_operations:[]});};
    await h.c.decideAgent(true);assert.equal(h.calls.length,1);
    await assert.rejects(h.c.AgentAPI.approveTask('task',s.preview_id,'true'),/must be boolean/);assert.equal(h.calls.length,1);
});

test('awaiting Package remains risk-interactive while the task is busy; untrusted pending mappings are withheld',()=>{
    const h=harness(),{s}=boundPackage(h,'risks');h.state.busy=true;h.c.updateAgentControls();
    assert.equal(h.el('packageRiskIntent').disabled,false);assert.equal(h.el('approveAgent').disabled,true);
    s.pending_operations[1].arguments.destination='untrusted-mapping-secret';h.c.renderAgent(s);
    assert.doesNotMatch(h.el('agentActions').innerHTML,/untrusted-mapping-secret/);assert.equal(h.el('approveAgent').disabled,true);
});

test('transport defaults to real without an implicit Mock fallback',()=>{const context={window:{}};vm.runInNewContext(fs.readFileSync(path.join(base,'agent-api.js'),'utf8'),context);assert.equal(context.window.AgentAPI.mode,'real');});
