/* Real Chrome UI rehearsal + silent browser-frame recording. No fake responses. */
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const manifest=JSON.parse(await fs.readFile(process.argv[2],'utf8'));const out=path.join(manifest.root,'recording');await fs.mkdir(out);const traces=[],errors=[];
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--no-proxy-server','--disable-background-networking']});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});await context.route('https://**',r=>r.abort());
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  page.on('response',async r=>{if(r.url().includes('/api/agent/tasks')){try{traces.push({url:r.url(),method:r.request().method(),request:r.request().postData(),status:r.status(),body:await r.text()})}catch{}}});
  await page.goto(manifest.url);await page.waitForFunction(()=>document.getElementById('mapping').children.length===22);
  async function run(name,filming){
   const frames=[];let stopping=false;const began=Date.now();
   const loop=filming?(async()=>{while(!stopping){frames.push({ms:Date.now()-began,data:(await page.screenshot({type:'jpeg',quality:80})).toString('base64')});await wait(400)}})():null;
   try{
    if(filming)await wait(2500);
    await page.locator('#start').click();await page.waitForFunction(()=>!document.getElementById('approve').disabled,{},{timeout:90000});
    const tid=await page.evaluate('task.task_id');const before=await (await context.request.get(manifest.url.split('/demo/')[0]+'/api/agent/tasks/'+tid)).json();
    assert.equal(before.task.status,'awaiting_approval');assert.equal(before.pending_operations.filter(x=>x.tool==='copy_file').length,22);
    const versions=before.results.find(x=>x.tool==='compare_versions');assert.equal(versions.success,true);
    assert.deepEqual(versions.data.groups.flatMap(g=>g.documents.map(d=>d.filename)).sort(),['课程设计报告_v1.docx','课程设计报告_v2.docx','课程设计报告_v3.docx']);
    await fs.writeFile(path.join(out,name+'-preview.json'),JSON.stringify(before,null,2),{flag:'wx'});
    await page.screenshot({path:path.join(out,name+'-approval.png'),fullPage:true});
    if(filming){await wait(4000);await page.locator('#mapping').evaluate(el=>el.parentElement.scrollTo({top:180,behavior:'smooth'}));await wait(2500);await page.locator('#mapping').evaluate(el=>el.parentElement.scrollTop=0);await page.locator('#approve').scrollIntoViewIfNeeded();await wait(1500)}
    await page.locator('#approve').click();
    await page.waitForFunction(()=>document.getElementById('verified').textContent==='22',{},{timeout:90000});
    const result=await page.evaluate('audit');assert.equal(result.status,'controlled_pass');assert.equal(result.original_22_unchanged,true);assert.ok(Object.values(result.checks).every(Boolean));
    await fs.writeFile(path.join(out,name+'-result.json'),JSON.stringify(result,(_,v)=>typeof v==='bigint'?v.toString():v,2),{flag:'wx'});
    await page.locator('#final').scrollIntoViewIfNeeded();if(filming)await wait(5000);
    await page.screenshot({path:path.join(out,name+'-completed.png'),fullPage:true});
    if(filming){await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));await wait(3500)}
    console.log(JSON.stringify({take:name,task_id:tid,status:result.status,copies:result.copies.length,source_unchanged:result.checks.source_22_unchanged,original_unchanged:result.original_22_unchanged}));
   }finally{stopping=true;if(loop)await loop;}
   return frames;
  }
  async function fresh(){await Promise.all([page.waitForEvent('load'),page.locator('#next').click()]);await page.waitForFunction(()=>document.getElementById('mapping').children.length===22);}
  await run('rehearsal',false);await fresh();
  const frames=await run('take1',true);assert.ok(frames.length>10);
  const raw=path.join(out,'frames');await fs.mkdir(raw);for(let i=0;i<frames.length;i++)await fs.writeFile(path.join(raw,String(i).padStart(4,'0')+'.jpg'),Buffer.from(frames[i].data,'base64'));
  await fs.writeFile(path.join(out,'frame-timing.json'),JSON.stringify(frames.map((f,i)=>({file:String(i).padStart(4,'0')+'.jpg',ms:f.ms})),null,2));
  // Encode actual timed screenshots using Chrome's native MediaRecorder, no ffmpeg dependency.
  const encoder=await context.newPage();await encoder.goto('about:blank');
  const video=await encoder.evaluate(async frames=>{
   const canvas=document.createElement('canvas');canvas.width=1440;canvas.height=1000;document.body.append(canvas);const ctx=canvas.getContext('2d');
   const mime='video/webm;codecs=vp8';if(!MediaRecorder.isTypeSupported(mime))throw Error('Browser cannot encode VP8');
   const stream=canvas.captureStream(5),recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:2200000}),chunks=[];
   recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};const ended=new Promise(r=>recorder.onstop=r);recorder.start();
   for(let i=0;i<frames.length;i++){const image=new Image();image.src='data:image/jpeg;base64,'+frames[i].data;await image.decode();ctx.drawImage(image,0,0);await new Promise(r=>setTimeout(r,i+1<frames.length?Math.max(80,frames[i+1].ms-frames[i].ms):1500))}
   recorder.stop();await ended;stream.getTracks().forEach(t=>t.stop());const bytes=new Uint8Array(await new Blob(chunks,{type:mime}).arrayBuffer());let text='';for(let i=0;i<bytes.length;i+=32768)text+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(text);
  },frames);
  await fs.writeFile(path.join(out,'Digital-Life-Organizer-22-files.webm'),Buffer.from(video,'base64'),{flag:'wx'});
  await fresh();const ready=await (await context.request.get(manifest.url.split('/demo/')[0]+'/demo/course22/context')).json();await fs.writeFile(path.join(out,'ready-for-next-recording.json'),JSON.stringify(ready,null,2));
  assert.deepEqual(errors,[]);await fs.writeFile(path.join(out,'http-trace.json'),JSON.stringify(traces,null,2));
  const creates=traces.filter(t=>t.method==='POST'&&t.url.endsWith('/api/agent/tasks'));const approvals=traces.filter(t=>t.method==='POST'&&t.url.endsWith('/approve'));
  assert.equal(creates.length,2);assert.equal(approvals.length,2);assert.ok(approvals.every(t=>t.status===200));
  console.log(JSON.stringify({video:path.join(out,'Digital-Life-Organizer-22-files.webm'),frames:frames.length,actual_seconds:frames.at(-1).ms/1000,tasks:creates.length,approvals:approvals.length,page_errors:errors,ready_workspace:ready.workspace}));
 }finally{await fs.writeFile(path.join(out,'http-trace-partial.json'),JSON.stringify(traces,null,2));await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
