/* Explicit live recovery acceptance: authorized source copies, real browser/API, no Planner override. */
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
const digest=raw=>crypto.createHash('sha256').update(raw).digest('hex');
async function inventory(root){const out={};for(const entry of await fs.readdir(root,{withFileTypes:true})){if(!entry.isFile())continue;const file=path.join(root,entry.name),st=await fs.stat(file,{bigint:true});out[entry.name]={sha256:digest(await fs.readFile(file)),bytes:st.size.toString(),mtime_ns:st.mtimeNs.toString()};}return out;}
(async()=>{
 assert.ok(process.argv.includes('--run'),'Explicit --run required: real model and approved file copies in a fresh temporary Workspace.');
 const source=path.resolve(process.argv[process.argv.indexOf('--run')+1]);
 const original=await inventory(source);assert.equal(Object.keys(original).length,22,'Expected the authorized 22-file course source');
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'dlo-course-recovery-check-')),workspace=path.join(root,'workspace');await fs.mkdir(workspace);
 for(const name of Object.keys(original))await fs.copyFile(path.join(source,name),path.join(workspace,name),require('node:fs').constants.COPYFILE_EXCL);
 const before=await inventory(workspace);for(const name of Object.keys(before))assert.equal(before[name].sha256,original[name].sha256);
 await fs.writeFile(path.join(root,'baseline.json'),JSON.stringify({source,workspace,original,workspace_before:before},null,2),{flag:'wx'});
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--no-proxy-server','--disable-background-networking']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[],responses=[];let tid=null;
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/agent/tasks'))requests.push({url:r.url(),method:r.method(),body:r.postData()});});
 page.on('response',async r=>{if(r.url().includes('/api/agent/tasks'))try{responses.push({url:r.url(),status:r.status(),body:await r.text()});}catch{}});
 await page.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||!['61779','8000','51851'].includes(u.port))return route.abort();return route.continue();});
 try{
  await page.goto('http://127.0.0.1:61779/course-workspace');await page.waitForFunction(()=>typeof apiReady!=='undefined'&&apiReady);
  await page.locator('#workspace').fill(workspace);await page.locator('#goal').fill('请根据当前目录实际读取的课程设计提交要求，整理全部22份课程材料，比较三份报告版本，并按要求中的用途分类复制归档。保留所有原件，不移动、不删除、不覆盖；先展示整理方案，获得确认后再执行。');
  await page.waitForFunction(()=>!document.getElementById('start').disabled);await page.locator('#start').click();
  console.log(JSON.stringify({phase:'started',workspace,evidence:root}));
  await page.waitForFunction(()=>snapshot&&['awaiting_approval','failed'].includes(snapshot.task.status),{},{timeout:120000});
  const preview=await page.evaluate(()=>({task,snapshot,analysis:document.getElementById('analysis').innerText,error:document.getElementById('error').innerText}));tid=preview.task.task_id;
  await fs.writeFile(path.join(root,'preview.json'),JSON.stringify(preview,(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});
  assert.equal(preview.snapshot.task.status,'awaiting_approval',preview.error||preview.snapshot.error);
  await page.waitForFunction(()=>!document.getElementById('approve').disabled,{},{timeout:15000});
  assert.match(preview.analysis,/已扫描工作空间/);assert.match(preview.analysis,/已读取课程要求/);assert.match(preview.analysis,/已比较/);
  const pending=preview.snapshot.pending_operations,copies=pending.filter(s=>s.tool==='copy_file');assert.equal(copies.length,22);assert.equal(new Set(copies.map(s=>s.arguments.source)).size,22);assert.equal(await page.locator('#mapping tr').count(),22);
  for(const copy of copies){assert.equal(path.dirname(copy.arguments.source),workspace);const relative=path.relative(workspace,copy.arguments.destination);assert.ok(relative&&!relative.startsWith('..')&&!path.isAbsolute(relative));assert.equal(relative.split(path.sep)[0],'课程设计_智能整理结果');}
  assert.deepEqual(await inventory(workspace),before);await assert.rejects(fs.stat(path.join(workspace,'课程设计_智能整理结果')),{code:'ENOENT'});
  console.log(JSON.stringify({phase:'real_preview',task_id:tid,rows:copies.length,approval_enabled:true,output_before_approval:false}));
  await page.locator('#approve').click();await page.waitForFunction(()=>audit||snapshot?.task.status==='failed',{},{timeout:120000});
  const value=await page.evaluate(()=>({audit,snapshot,error:document.getElementById('error').innerText}));assert.equal(value.snapshot.task.status,'completed',value.error||value.snapshot.error);assert.equal(value.audit?.status,'controlled_pass',value.error);assert.ok(Object.values(value.audit.checks).every(Boolean));
  const verified=[];for(const copy of copies){const target=copy.arguments.destination;assert.equal(digest(await fs.readFile(target)),before[path.basename(copy.arguments.source)].sha256);verified.push({source:copy.arguments.source,target,sha256:digest(await fs.readFile(target))});}
  assert.deepEqual(await inventory(workspace),before);assert.deepEqual(await inventory(source),original);assert.equal(await page.locator('#copied').innerText(),'22');assert.equal(await page.locator('#verified').innerText(),'22');assert.equal(await page.locator('#courseFlow .cf-node').count(),9);
  await page.waitForFunction(()=>document.getElementById('courseFlowStatus').textContent==='流程展示结束',{},{timeout:15000});
  assert.equal(errors.length,0);assert.equal(requests.filter(r=>r.method==='POST'&&new URL(r.url).pathname==='/api/agent/tasks').length,1);assert.equal(requests.filter(r=>r.method==='POST'&&r.url.endsWith('/approve')).length,1);
  assert.equal(new URL(requests.find(r=>r.method==='POST'&&r.url.endsWith('/approve')).url).pathname,`/api/agent/tasks/${tid}/approve`);
  assert.equal(JSON.parse(requests.find(r=>r.url.endsWith('/approve')).body).preview_id,preview.snapshot.preview_id);
  const record={status:'real_course22_browser_pass',task_id:tid,workspace,source,verified_copies:verified,original_22_unchanged:true,test_sources_unchanged:true,checks:value.audit.checks,audit:value.audit,requests,page_errors:errors,flow_nodes:9};
  await fs.writeFile(path.join(root,'acceptance.json'),JSON.stringify(record,(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});
  console.log(JSON.stringify({status:record.status,task_id:tid,copies:verified.length,source_unchanged:true,workspace,evidence:root,checks:value.audit.checks}));
 }catch(error){await fs.writeFile(path.join(root,'failure.json'),JSON.stringify({task_id:tid,error:error.message,requests,responses,page_errors:errors},null,2),{flag:'wx'});throw Error(error.message+'; evidence: '+root);}
 finally{await fs.writeFile(path.join(root,'responses.json'),JSON.stringify(responses,null,2),{flag:'wx'});await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
