/* Explicit opt-in live acceptance. Never approves writes; no fixed Planner. */
'use strict';
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
async function main(){
 if(process.argv.includes('--inspect')){
  const tid=process.argv[process.argv.indexOf('--inspect')+1];assert.match(tid,/^task_[a-zA-Z0-9_-]+$/);
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--no-proxy-server','--disable-background-networking']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||u.port!=='8000'||/\/(approve|reject)$/.test(u.pathname))return route.abort();return route.continue();});
  await page.goto('http://127.0.0.1:8000/');
  console.log(JSON.stringify(await page.evaluate(async tid=>{AgentAPI.setMode('real');agentState.mode='real';const s=await AgentAPI.getTask(tid);if(s.task.task_id!==tid)throw Error('Wrong task response');agentState.task=s.task;agentState.taskContext={...s.task};agentWorkspacePath.value=s.task.workspace;agentGoal.value=s.task.user_goal;agentInteractive.checked=true;await applyAgentSnapshot(s);return {task_id:s.task.task_id,status:s.task.status,restored_from:'real GET Snapshot',new_tasks:0};},tid)));
  await page.locator('#agentFlowVisualization').scrollIntoViewIfNeeded();
  console.log('Existing real task opened; no task created. Approve/reject requests blocked.');
  await new Promise(resolve=>browser.on('disconnected',resolve));return;
 }
 if(!process.argv.includes('--run'))throw Error('Use --run explicitly: this creates one real model-backed task in a new temporary Workspace.');
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'dlo-real-agent-')),workspace=path.join(root,'workspace');await fs.mkdir(workspace);
 const documents={
  '要求.txt':'课程项目提交要求：请提交一份最终报告。报告目前有v1和v2两个版本，提交哪份由用户决定。需要先读取正文并比较版本；不能仅凭文件名自动采用。文件操作前必须独立审批。',
  '报告_v1.txt':'课程项目报告\n版本：v1\n实验样本数量：10\n结果：初步测试完成。\n状态：历史草稿，尚未确认用于提交。',
  '报告_v2.txt':'课程项目报告\n版本：v2\n实验样本数量：20\n结果：补充测试完成。\n状态：新候选版本，是否作为最终提交稿需用户决定。'
 };
 for(const [name,body]of Object.entries(documents))await fs.writeFile(path.join(workspace,name),body,{encoding:'utf8',flag:'wx'});
 const before={};for(const name of Object.keys(documents)){const raw=await fs.readFile(path.join(workspace,name));before[name]=crypto.createHash('sha256').update(raw).digest('hex');}
 console.log(JSON.stringify({phase:'prepared',workspace,evidence:root,files:Object.keys(documents).length}));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--no-proxy-server','--disable-background-networking']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[],history=[];let stopped=false,rawIndex=0;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{const req=route.request(),u=new URL(req.url());if(u.hostname!=='127.0.0.1'||u.port!=='8000')return route.abort();if(/\/(approve|reject)$/.test(u.pathname))return route.abort();requests.push({method:req.method(),path:u.pathname});return route.continue();});
 page.on('response',async response=>{if(/^http:\/\/127\.0\.0\.1:8000\/api\/agent\/tasks\/[^/]+$/.test(response.url())){try{const raw=await response.text();await fs.writeFile(path.join(root,`snapshot-${++rawIndex}.json`),raw,{flag:'wx'});}catch{}}});
 try{
  await page.goto('http://127.0.0.1:8000/');await page.locator('#agentWorkspacePath').fill(workspace);await page.locator('#agentInteractive').check();
  await page.locator('#agentGoal').fill('请读取本目录三份TXT的真实正文，提取提交要求并比较两份报告的版本关系；如果最终选材不明确请通过材料澄清问我。确定后提出创建本工作空间下“待审批输出”目录、复制我确认的报告的具体方案。不要移动、删除、覆盖；不要自动批准。');
  await page.locator('#runAgent').click();
  let previous='';const deadline=Date.now()+120000;
  while(Date.now()<deadline){
   const state=await page.evaluate(()=>({task:agentState.task,snapshot:agentState.snapshot,report:agentState.report,stages:[...document.querySelectorAll('.agent-flow-stage')].map(n=>({key:n.dataset.stage,status:n.dataset.status,current:n.dataset.current}))}));
   const signature=JSON.stringify({status:state.task?.status,results:state.snapshot?.results?.length,stages:state.stages});
   if(signature!==previous){history.push(state);previous=signature;console.log(JSON.stringify({phase:'observed',task_id:state.task?.task_id,status:state.task?.status,results:state.snapshot?.results?.length,stage:state.stages.find(n=>n.current==='true')?.key}));}
   if(['awaiting_clarification','awaiting_approval','failed','completed'].includes(state.task?.status)){stopped=true;break;}
   await page.waitForTimeout(250);
  }
  assert.ok(stopped,'Real task did not reach a stable checkpoint within 120s');
  const state=history.at(-1),snapshot=state.snapshot;
  assert.equal(errors.length,0,'Page errors');
  assert.ok(!requests.some(r=>/\/(approve|reject)$/.test(r.path)),'No decisions allowed');
  assert.equal(state.report,null,'No final report before approval');
  const names=await fs.readdir(workspace);assert.deepEqual(names.sort(),Object.keys(documents).sort(),'No file operations before approval');
  for(const name of names){assert.equal(crypto.createHash('sha256').update(await fs.readFile(path.join(workspace,name))).digest('hex'),before[name]);}
  const summary={workspace,evidence:root,task_id:state.task?.task_id,status:state.task?.status,error:snapshot?.error,
   tools:(snapshot?.results||[]).map(r=>({tool:r.tool,success:r.success})),planner_events:(snapshot?.planner_events||[]).map(({model,provider_host,status,duration_ms,response_id,usage})=>({model,provider_host,status,duration_ms,response_id,usage})),
   stages:state.stages,original_sha256:before,originals_unchanged:true,approval_requests:0,page_errors:errors,
   horizontal_overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),
   result_completed:state.stages.some(n=>n.key==='result'&&n.status==='completed')};
  await fs.writeFile(path.join(root,'acceptance.json'),JSON.stringify(summary,null,2),{flag:'wx'});
  await fs.writeFile(path.join(root,'history.json'),JSON.stringify(history,(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});
  console.log(JSON.stringify({phase:'checkpoint',...summary}));
  console.log('Browser left open for inspection. No approval will be submitted.');
  await new Promise(resolve=>browser.on('disconnected',resolve));
 }catch(error){console.error('Acceptance stopped: '+error.message);await browser.close();process.exitCode=1;}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
