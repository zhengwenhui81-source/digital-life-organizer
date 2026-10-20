const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const base = path.resolve(__dirname,'..');

function harness(mode='real') {
    const elements=new Map(), timers=new Map(), calls=[]; let timerId=0;
    const el=id=>{
        if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',hidden:false,disabled:false,dataset:{},style:{},listeners:{},classList:{add(){},remove(){},toggle(){}},addEventListener(k,v){this.listeners[k]=v;},setAttribute(k,v){this[k]=v;},querySelectorAll(){return[];},appendChild(){},remove(){}});
        return elements.get(id);
    };
    const c={window:{},console,AbortController,document:{getElementById:el,querySelectorAll:()=>[],createElement:()=>el('toast')},navigator:{clipboard:{writeText:async()=>{}}},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),setInterval(){throw Error('Unexpected interval');},clearInterval(){},fetch:async(url,options)=>{if(!url.startsWith('/api/agent/'))return {ok:false};calls.push({url,options});return c.respond(url,options);}};
    vm.createContext(c);
    for(const file of ['agent-api.js','agent-mock.js','agent-results.js','organization-preview.js','organization-demo.js'])vm.runInContext(fs.readFileSync(path.join(base,file),'utf8'),c);
    c.AgentAPI=c.window.AgentAPI;c.AgentMock=c.window.AgentMock;c.AgentResults=c.window.AgentResults;
    c.OrganizationPreview=c.window.OrganizationPreview;c.OrganizationDemo=c.window.OrganizationDemo;
    vm.runInContext(fs.readFileSync(path.join(base,'index.html'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1],c);
    vm.runInContext('window.state=agentState',c);
    el('agentMode').value=mode;el('agentScenario').value='happy';el('agentWorkspacePath').value='E:/unknown-workspace';el('agentGoal').value='准备课程材料';
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
test('every organization preview sends no requests and material Mock happy path still completes',async()=>{
    const h=harness();h.c.switchAgentWorkflow('organization');assert.equal(h.el('organizationWorkspace').hidden,false);assert.equal(h.el('materialWorkspace').hidden,true);
    for(const scenario of ['mixed','single','empty','unknown','collision','incomplete']){
        h.el('organizationScenario').value=scenario;h.c.showOrganizationPreview();assert.ok(h.el('organizationPreview').innerHTML.length>0);
    }
    h.c.showOrganizationPreview(true);assert.match(h.el('organizationPreview').innerHTML,/尚未开始/);
    h.c.switchAgentWorkflow('materials');assert.equal(h.el('materialWorkspace').hidden,false);assert.equal(h.calls.length,0);
    h.el('agentMode').value='mock';await h.c.runAgent();for(let i=0;i<5;i++)await h.c.pollAgent();
    assert.equal(h.state.task.status,'awaiting_approval');await h.c.decideAgent(true);for(let i=0;i<3;i++)await h.c.pollAgent();
    assert.equal(h.state.task.status,'completed');assert.equal(h.calls.length,0);
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

test('unintegrated real Package approval and success presentation stay blocked, rejection remains available',async()=>{
    const h=harness();seedTask(h,'awaiting_approval');
    h.c.renderAgent(snapshot('awaiting_approval',{preview_id:'package-preview',results:[{tool:'plan_package',success:true,data:{},message:'plan only',error:null}]}));
    assert.equal(h.el('approveAgent').disabled,true);assert.equal(h.el('rejectAgent').disabled,false);
    assert.match(h.el('agentActions').innerHTML,/accept_incomplete 尚未接通/);
    await h.c.decideAgent(true);assert.equal(h.calls.length,0);assert.match(h.el('agentErrorDetail').textContent,/不会发送批准请求/);
    h.c.AgentAPI.rejectTask=async(id,preview)=>{assert.equal(id,'task');assert.equal(preview,'package-preview');return snapshot('failed',{error:'Rejected'});};
    await h.c.decideAgent(false);assert.equal(h.state.task.status,'failed');assert.equal(h.state.userRejected,true);
    seedTask(h);assert.throws(()=>h.c.renderAgentReport({task_id:'task',status:'completed',package_path:'E:/package'}),/Package 报告集成尚未验收/);
    assert.equal(h.state.report,null);
});
