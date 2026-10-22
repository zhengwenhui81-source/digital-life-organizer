/* Opt-in real model/browser/filesystem acceptance, only in a new synthetic Workspace. */
'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
async function inventory(workspace,names){const out={};for(const name of names){const file=path.join(workspace,name),st=await fs.stat(file,{bigint:true});out[name]={sha256:sha(await fs.readFile(file)),size:st.size.toString(),mtime_ns:st.mtimeNs.toString()};}return out;}
async function main(){
 assert.ok(process.argv.includes('--run'),'Explicit --run required; this makes real model requests and approves copies in a NEW temporary test Workspace only.');
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'dlo-complete-e2e-')),workspace=path.join(root,'workspace');await fs.mkdir(workspace);
 const docs={
  '说明.txt':'项目报告归档说明：附件A和附件B是同一项目报告的两份候选稿，最终采用哪份必须请用户确认。其他材料并不是项目报告，应按实际用途整理。请先读正文，不凭文件名归类；保留所有原始文件。',
  '附件A.txt':'项目报告\n版本v1，历史草稿\n实验样本10份，初步结果，未确认提交。',
  '附件B.txt':'项目报告\n版本v2，新候选稿\n实验样本20份，补充验证结果，最终采用需用户确认。',
  '记录甲.txt':'公司日常经费报销凭据\n用途：办公用品采购报销。金额人民币112元。财务审核待处理。本文件不属于项目报告。',
  '清单乙.txt':'出差行程安排\n目的地杭州，周一高铁出发，周二返程。用途为出行安排，不是财务票据，也不是项目报告。'
 };
 for(const [name,body] of Object.entries(docs))await fs.writeFile(path.join(workspace,name),body,{encoding:'utf8',flag:'wx'});
 const names=Object.keys(docs),before=await inventory(workspace,names),history=[],http=[],pageErrors=[];let tid=null,index=0;
 await fs.writeFile(path.join(root,'baseline.json'),JSON.stringify({workspace,files:before,gold:{selected_report:'附件B.txt',retain_only:['说明.txt','附件A.txt'],separate_purposes:['项目报告','财务报销','出差行程']}},null,2),{flag:'wx'});
 console.log(JSON.stringify({phase:'prepared',root,workspace,files:names.length}));
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:false,args:['--no-proxy-server','--disable-background-networking']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>pageErrors.push(e.message));
 await page.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||u.port!=='8000')return route.abort();if(r.method()!=='GET'&&!((u.pathname==='/api/agent/tasks'&&!tid)||(tid&&[`${'/api/agent/tasks/'}${tid}/answers`,`${'/api/agent/tasks/'}${tid}/approve`].includes(u.pathname))))return route.abort();http.push({method:r.method(),path:u.pathname,body:r.postData()});return route.continue();});
 page.on('response',async r=>{if(/^http:\/\/127\.0\.0\.1:8000\/api\/agent\/tasks\/[^/]+(?:\/report)?$/.test(r.url()))try{await fs.writeFile(path.join(root,`response-${++index}.json`),await r.text(),{flag:'wx'});}catch{}});
 const observe=async()=>page.evaluate(()=>({task:agentState.task,snapshot:agentState.snapshot,report:agentState.report,
  stages:[...document.querySelectorAll('.agent-flow-stage')].map(n=>({key:n.dataset.stage,status:n.dataset.status,current:n.dataset.current}))}));
 const wait=async()=>{const until=Date.now()+120000;let last='';while(Date.now()<until){const state=await observe();const sig=JSON.stringify({status:state.task?.status,n:state.snapshot?.results?.length,stages:state.stages});if(sig!==last){history.push(state);last=sig;console.log(JSON.stringify({phase:'state',task:state.task?.task_id,status:state.task?.status,results:state.snapshot?.results?.length}));}if(['awaiting_clarification','awaiting_approval','failed','completed'].includes(state.task?.status)){tid=state.task.task_id;return state;}await page.waitForTimeout(250);}throw Error('Task checkpoint timed out');};
 try{
  await page.goto('http://127.0.0.1:8000/');await page.locator('#agentWorkspacePath').fill(workspace);await page.locator('#agentGoal').fill('请读取当前工作空间的全部可读文件正文，识别实际用途并比较项目报告版本。文件名可能没有用途信息，不要靠文件名猜分类。选哪个报告有歧义，请向我澄清。确认选材后，在当前工作空间内提出“整理结果”及用途分类子目录、具体复制映射，保留原件。说明文件不用归档。禁止移动、删除和覆盖，必须在审批后才创建目录和复制。');await page.locator('#agentInteractive').check();await page.locator('#runAgent').click();
  let state=await wait();assert.equal(state.task.status,'awaiting_clarification',state.snapshot?.error||'Expected actual model clarification');const sameTask=tid;
  const answer='项目报告采用正文版本v2的新候选稿；v1历史草稿保留原处且不复制。其他两份资料分别按正文的财务报销凭据和出差行程用途归档到不同类别。说明文件保留原处且不复制。输出放本工作空间的“整理结果”目录，各用途子目录名称由你根据正文确定。请生成具体目录和复制方案，文件操作仍须另行审批。';
  for(let round=0;state.task.status==='awaiting_clarification'&&round<2;round++){
   const fields=page.locator('#agentClarification textarea');assert.equal(await fields.count(),state.snapshot.clarification.questions.length);for(let i=0;i<await fields.count();i++)await fields.nth(i).fill(answer);
   await page.getByRole('button',{name:'提交回答并继续规划'}).click();await page.waitForFunction(()=>agentState.task?.status!=='awaiting_clarification',{},{timeout:30000});state=await wait();assert.equal(tid,sameTask,'Continuation must use same task');
  }
  assert.equal(state.task.status,'awaiting_approval',state.snapshot?.error||'No approved execution plan');assert.ok(state.snapshot.preview_id);
  const pending=state.snapshot.pending_operations;assert.ok(pending.length>0);assert.ok(pending.every(s=>['create_folder','copy_file'].includes(s.tool)));
  const copies=pending.filter(s=>s.tool==='copy_file');assert.equal(copies.length,3,'Gold set has three selected source files');assert.deepEqual(copies.map(s=>path.basename(s.arguments.source)).sort(),['附件B.txt','记录甲.txt','清单乙.txt'].sort());assert.equal(new Set(copies.map(s=>path.dirname(s.arguments.destination))).size,3,'Actual purposes require separate category directories');
  for(const operation of pending){const dest=operation.tool==='copy_file'?operation.arguments.destination:operation.arguments.path,relative=path.relative(workspace,path.resolve(dest));assert.ok(relative&&!relative.startsWith('..')&&!path.isAbsolute(relative));assert.equal(relative.split(path.sep)[0],'整理结果');await assert.rejects(fs.stat(dest),{code:'ENOENT'});}
  assert.deepEqual(await inventory(workspace,names),before);assert.deepEqual((await fs.readdir(workspace)).sort(),names.sort());
  await fs.writeFile(path.join(root,'frozen-preview.json'),JSON.stringify(state,(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});
  console.log(JSON.stringify({phase:'approval_checkpoint',task:tid,preview_id:state.snapshot.preview_id,copies:copies.map(s=>({source:s.arguments.source,destination:s.arguments.destination})),originals_unchanged:true}));
  // Pause to allow the user to inspect the actual browser preview; this test is explicitly authorized.
  await page.waitForTimeout(15000);
  const button=page.locator('#approveAgent');assert.equal(await button.isEnabled(),true);await button.click();
  await page.waitForFunction(()=>agentState.task?.status!=='awaiting_approval'&&!agentState.decisionBusy,{},{timeout:60000});state=await wait();assert.equal(tid,sameTask);assert.equal(state.task.status,'completed',state.snapshot?.error);await page.waitForFunction(()=>agentState.report?.task_id===agentState.task?.task_id,{},{timeout:30000});state=await observe();assert.equal(state.report.status,'completed');
  const verified=[];for(const copy of copies){const source=await fs.readFile(copy.arguments.source),destination=await fs.readFile(copy.arguments.destination);assert.equal(sha(source),sha(destination));verified.push({source:copy.arguments.source,destination:copy.arguments.destination,sha256:sha(destination),bytes:destination.length});}
  assert.deepEqual(await inventory(workspace,names),before);const output=await fs.readdir(path.join(workspace,'整理结果'),{recursive:true});const actualFiles=[];for(const item of output)if((await fs.stat(path.join(workspace,'整理结果',item))).isFile())actualFiles.push(item);assert.equal(actualFiles.length,3,'No unexpected duplicate copies');
  const checks=state.snapshot.results.filter(r=>r.tool==='verify_result');assert.ok(checks.length&&checks.at(-1).success&&checks.at(-1).data.passed);assert.ok(state.snapshot.results.some(r=>r.tool==='compare_versions'&&r.success));assert.equal(state.report.operations.filter(r=>r.tool==='copy_file'&&r.success).length,3);
  for(const key of ['scan','read','versions','plan','execute','verify','result'])assert.equal(state.stages.find(s=>s.key===key)?.status,'completed',key+' graph evidence');assert.equal(pageErrors.length,0);
  await page.locator('[data-stage="execute"] .agent-flow-details summary').click();assert.ok(await page.locator('[data-stage="execute"] .agent-flow-details pre').innerText());
  const record={status:'real_browser_model_execution_pass',task_id:tid,workspace,model_events:(state.snapshot.planner_events||[]).map(({model,provider_host,status,response_id,usage,duration_ms})=>({model,provider_host,status,response_id,usage,duration_ms})),originals_unchanged:true,verified_copies:verified,output_file_count:actualFiles.length,server_verification:checks.at(-1),report:state.report,stages:state.stages,page_errors:pageErrors,http,history};
  await fs.writeFile(path.join(root,'acceptance.json'),JSON.stringify(record,(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});console.log(JSON.stringify({phase:'passed',task:tid,workspace,evidence:root,copies:verified,model_calls:record.model_events.length,page_errors:pageErrors.length}));
  console.log('Browser left open on the actual final report.');await new Promise(resolve=>browser.on('disconnected',resolve));
 }catch(error){await fs.writeFile(path.join(root,'failure.json'),JSON.stringify({error:error.message,task:tid,history,http,pageErrors},(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});console.error(JSON.stringify({phase:'failed',error:error.message,evidence:root,task:tid}));await browser.close();process.exitCode=1;}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
