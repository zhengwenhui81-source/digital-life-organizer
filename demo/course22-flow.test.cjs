const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'course22.html'),'utf8');
const script=html.match(/<script id="course-flow-script">([\s\S]*?)<\/script>/)[1];
const context={module:{exports:{}}};vm.runInNewContext(script,context);
const {createFlow,titles}=context.module.exports;
function harness(){let state,id=0;const timers=new Map();const flow=createFlow(s=>state=s,f=>{timers.set(++id,f);return id;},n=>timers.delete(n));return {flow,timers,get state(){return state;},tick(){const [n,f]=timers.entries().next().value;timers.delete(n);f();}};}
test('nine display stages are isolated from all Agent and file APIs',()=>{assert.equal(titles.length,9);assert.doesNotMatch(script,/fetch\(|AgentAPI|\.onclick\s*=|preventDefault|stopPropagation/);const h=harness();h.flow.reset();assert.equal(h.state.phase,'idle');assert.equal(h.state.progress,0);assert.ok(h.state.states.every(s=>s==='pending'));});
test('Run display advances to confirmation and waits without any execution request',()=>{const h=harness();h.flow.start();assert.equal(h.state.states[0],'active');for(let i=0;i<5;i++)h.tick();assert.equal(h.state.index,5);assert.equal(h.state.phase,'waiting');assert.equal(h.timers.size,0);assert.equal(h.state.states[6],'pending');});
test('confirmation advances only the visual sequence and ends at 100 percent',()=>{const h=harness();h.flow.start();h.flow.confirm();assert.equal(h.state.index,6);h.tick();h.tick();assert.equal(h.state.phase,'finished');assert.equal(h.state.progress,100);assert.ok(h.state.states.every(s=>s==='done'));});
test('reset cancels timers and stale callbacks cannot affect a new selection',()=>{const h=harness();h.flow.start();const stale=[...h.timers.values()][0];h.flow.reset();stale();assert.equal(h.state.phase,'idle');assert.equal(h.state.index,-1);assert.equal(h.timers.size,0);});
test('visible error/rejection stops animation and cannot resume itself',()=>{const h=harness();h.flow.start();h.flow.fail();assert.equal(h.state.phase,'failed');assert.equal(h.state.states[0],'failed');assert.equal(h.timers.size,0);h.flow.confirm();assert.equal(h.state.phase,'failed');});

test('Chrome visual-only flow: start, waiting, confirm, narrow layout; existing metrics unchanged; zero requests',{timeout:30000},async()=>{
 const {chromium}=require(path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-background-networking']});
 try{for(const width of [1440,390]){const page=await browser.newPage({viewport:{width,height:1000}});let requests=0;await page.route('**/*',r=>{requests++;return r.abort();});
  await page.setContent(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
  await page.evaluate(()=>{window.flowTimers=new Map();let id=0;window.setTimeout=f=>{flowTimers.set(++id,f);return id;};window.clearTimeout=n=>flowTimers.delete(n);window.tickFlow=()=>{const [n,f]=flowTimers.entries().next().value;flowTimers.delete(n);f();};});
  await page.addScriptTag({content:script});await page.evaluate(()=>document.getElementById('start').disabled=false);await page.locator('#start').click();assert.equal(await page.locator('#courseFlow [data-state="active"]').count(),1);
  await page.evaluate(()=>{for(let i=0;i<5;i++)tickFlow();});assert.equal(await page.locator('#courseFlow [data-state="waiting"]').count(),1);
  await page.evaluate(()=>document.getElementById('approve').disabled=false);await page.locator('#approve').click();await page.evaluate(()=>{tickFlow();tickFlow();});
  assert.equal(await page.locator('#courseFlow [data-state="done"]').count(),9);assert.equal(await page.locator('#copied').innerText(),'—');assert.equal(await page.locator('#verified').innerText(),'—');assert.match(await page.locator('#result').innerText(),/尚未执行/);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.equal(requests,0);await page.close();
 }}finally{await browser.close();}
});

test('original page binding: early input survives deferred context; failed task replaces waiting placeholders; foreign task is rejected',{timeout:30000},async()=>{
 const {chromium}=require(path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{const page=await browser.newPage();let network=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>{network++;return r.abort();});
  await page.setContent(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,''));
  await page.evaluate(()=>{window.AgentAPI={request:async()=>{},getTask:async()=>{throw Error('Unexpected task request');}};window.fetch=async url=>url==='/demo/course22/context'?new Promise(resolve=>window.releaseContext=()=>resolve({ok:true,json:async()=>({backend_url:'http://127.0.0.1:8000'})})):{ok:true,json:async()=>({path:'C:/synthetic-course-workspace'})};});
  await page.addScriptTag({content:html.match(/<script>([\s\S]*?)<\/script>/)[1]});
  await page.locator('#workspace').fill('C:/synthetic-course-workspace');await page.locator('#goal').fill('synthetic course goal');assert.equal(await page.locator('#start').isDisabled(),true);
  await page.evaluate(()=>releaseContext());await page.waitForFunction(()=>!document.getElementById('start').disabled);
  assert.equal(await page.locator('#workspace').inputValue(),'C:/synthetic-course-workspace');assert.equal(await page.locator('#goal').inputValue(),'synthetic course goal');
  await page.evaluate(async()=>{task={task_id:'fixture-task'};snapshot={task:{task_id:'fixture-task',workspace:context.workspace,status:'failed'},plan:null,results:[],pending_operations:[],error:'synthetic connection failed'};await render();});
  assert.match(await page.locator('#analysis').innerText(),/任务已失败/);assert.match(await page.locator('#mapping').innerText(),/任务已失败/);assert.match(await page.locator('#approval').innerText(),/任务失败/);assert.match(await page.locator('#result').innerText(),/文件操作未执行/);assert.equal(await page.locator('#approve').isDisabled(),true);
  const foreign=await page.evaluate(async()=>{AgentAPI.getTask=async()=>({task:{task_id:'foreign-task',workspace:context.workspace,status:'completed'}});try{await poll();return false;}catch(e){return e.message.includes('当前任务')&&snapshot.task.task_id==='fixture-task';}});
  assert.equal(foreign,true);assert.deepEqual(errors,[]);assert.equal(network,0);
 }finally{await browser.close();}
});
