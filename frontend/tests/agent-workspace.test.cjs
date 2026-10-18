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
