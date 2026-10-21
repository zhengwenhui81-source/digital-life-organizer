/* Installed Chrome + built-in Node CDP client; no dependency installation or HTTP server. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {mkdtemp,rm,readFile,writeFile,mkdir,readdir}=require('node:fs/promises');
const {createHash}=require('node:crypto');
const {tmpdir}=require('node:os');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
test('Opt-in real Windows HTTP observation (controlled planner, no substituted ToolResult)',{timeout:120000,skip:!process.env.PACKAGE_LIVE_MANIFEST},async()=>{
    const manifest=JSON.parse(await readFile(process.env.PACKAGE_LIVE_MANIFEST,'utf8'));
    assert.equal(manifest.kind,'controlled-plan-real-tools-not-LLM');
    assert.equal(path.isAbsolute(manifest.directory),true);
    assert.deepEqual(Object.keys(manifest.cases),['normal','missing','reject','changed','occupied','partial_source_changed','unrecognized_notice']);
    await assert.rejects(readFile(path.join(manifest.directory,'browser-evidence.json')),{code:'ENOENT'});
    assert.match(manifest.url,/^http:\/\/127\.0\.0\.1:\d+$/);
    const evidence={kind:manifest.kind,url:manifest.url,cases:[],status:'blocked',e2e:false};
    const profile=await mkdtemp(path.join(tmpdir(),'package-fixture-browser-'));
    const browser=spawn(process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--no-proxy-server','--disable-gpu','--no-first-run','--disable-background-networking','--disable-component-update','--disable-sync','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
    let ws;const observers=new Set();
    try{
        const endpoint=await new Promise((resolve,reject)=>{let log='';const timer=setTimeout(()=>reject(Error('Chrome startup timed out')),15000);browser.once('error',e=>{clearTimeout(timer);reject(e);});browser.stderr.on('data',d=>{log+=d;const match=log.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(match){clearTimeout(timer);resolve(match[1]);}});});
        ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
        let id=0;const pending=new Map(),network=[],pageErrors=[];
        ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}}else{if(m.method==='Network.requestWillBeSent')network.push(m.params.request);if(m.method==='Runtime.exceptionThrown')pageErrors.push(m.params.exceptionDetails);}};
        const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
        const {targetId}=await send('Target.createTarget',{url:'about:blank'});
        const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
        const call=(method,params)=>send(method,params,sessionId);

        await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
        await call('Network.setBlockedURLs',{urls:['https://*']});
        const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
        const open=async()=>{
            await call('Page.navigate',{url:manifest.url});
            await evaluate("new Promise(resolve=>{if(document.readyState==='complete')resolve();else addEventListener('load',resolve,{once:true})})");
            await evaluate("switchWorkspaceView('agent');agentMode.value='real';agentMode.dispatchEvent(new Event('change'))");
        };
        await open();
        const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
        let previousPreview=null;
        for(const [name,workspace] of Object.entries(manifest.cases)){
            assert.equal(path.dirname(workspace),manifest.directory);
            const original=await readFile(path.join(workspace,'报名表.txt')),originalHash=hash(original);
            await evaluate(`agentWorkspacePath.value=${JSON.stringify(workspace)};agentGoal.value='准备报名材料包，执行文件操作前让我确认';runAgent()`);
            let state;
            for(let n=0;n<80;n++){
                state=await evaluate("({status:agentState.task?.status,id:agentState.task?.task_id,error:agentState.snapshot?.error})");
                if(['awaiting_approval','failed'].includes(state.status))break;
                if(state.status==='completed'&&n>20)break;
                await new Promise(resolve=>setTimeout(resolve,100));
                await evaluate('pollAgent()');
            }
            assert.ok(state.id,'task created');
            const rawBefore=await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}).then(r=>r.text())`);
            const item={name,task_id:state.id,rawBefore,initial_status:state.status,error:state.error,source_sha256:originalHash,status:'blocked',copies:[]};evidence.cases.push(item);
            if(state.status==='awaiting_approval'){
                const preview=await evaluate('agentState.snapshot.preview_id');
                if(previousPreview){
                    item.cross_task_preview_status=await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}+'/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preview_id:${JSON.stringify(previousPreview)},accept_incomplete:true})}).then(r=>r.status)`);
                    assert.equal(item.cross_task_preview_status,409);assert.equal(await evaluate('agentState.snapshot.preview_id'),preview);
                }
                previousPreview=preview;
                const selected=await evaluate("PackagePreview.inspectSnapshot(agentState.snapshot,agentState.taskContext).input?.planResult.data.plan.selected_files.map(f=>({source:f.source.path,target:f.target}))");
                const destination=await evaluate("PackagePreview.inspectSnapshot(agentState.snapshot,agentState.taskContext).input?.planResult.data.plan.destination");
                const gate=await evaluate('PackagePreview.approval(agentState.snapshot,agentState.taskContext).ready');
                item.frontend_gate=gate;
                if(!gate){item.error='Backend preview exists, frontend conservatively rejected display/approval';}
                else{
                    // Page refresh: explicitly resume the same service-owned task.
                    await open();await evaluate(`agentResumeTask.value=${JSON.stringify(state.id)};resumeAgentTask()`);
                    assert.equal(await evaluate('agentState.task.task_id'),state.id);
                    if(name==='changed')await writeFile(path.join(workspace,'报名表.txt'),Buffer.concat([original,Buffer.from('\ncontrolled-source-change')]));
                    if(name==='occupied'){assert.equal(path.dirname(destination),workspace);await mkdir(destination);await writeFile(path.join(destination,'occupied-sentinel.txt'),'must not overwrite',{flag:'wx'});}
                    if(await evaluate('!packageRiskControl.hidden')){
                        item.without_acceptance_status=await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}+'/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preview_id:${JSON.stringify(preview)}})}).then(r=>r.status)`);
                        assert.equal(item.without_acceptance_status,409);
                    }
                    let observer;
                    if(name==='partial_source_changed'){
                        assert.equal(selected.length,2);for(const file of selected){assert.equal(path.dirname(file.source),workspace);assert.equal(path.dirname(file.target),destination);}
                        // Deliberately modify ONLY this run's second synthetic source after
                        // the first real copy exists. No backend result/algorithm patch.
                        const code="import pathlib,sys,time; first=pathlib.Path(sys.argv[1]); source=pathlib.Path(sys.argv[2]); print('armed',flush=True); end=time.monotonic()+15\nwhile time.monotonic()<end:\n if first.exists():\n  with source.open('ab') as f:f.write(b'controlled-after-first-copy-change')\n  break\n time.sleep(0.0001)";
                        observer=spawn(path.resolve('.venv/Scripts/python.exe'),['-B','-c',code,selected[0].target,selected[1].source],{windowsHide:true,stdio:['ignore','pipe','pipe']});
                        observers.add(observer);
                        await new Promise((resolve,reject)=>{observer.once('error',reject);observer.stdout.once('data',resolve);});
                    }
                    if(name==='reject')await evaluate('decideAgent(false)');
                    else{
                        if(await evaluate('!packageRiskControl.hidden')){assert.equal(await evaluate('packageRiskIntent.disabled'),false);await evaluate('packageRiskIntent.click()');assert.equal(await evaluate('packageRiskIntent.checked'),true);}
                        assert.equal(await evaluate('approveAgent.disabled'),false);
                        await evaluate("approveAgent.click();approveAgent.click();new Promise((resolve,reject)=>{let n=0;const wait=()=>!agentState.decisionBusy?resolve():++n>300?reject(Error('Approval response timed out')):setTimeout(wait,100);wait()})");
                    }
                    if(observer){observer.kill();await new Promise(resolve=>observer.exitCode!==null?resolve():observer.once('exit',resolve));}
                    item.final_status=await evaluate('agentState.task.status');
                    item.ui_success=await evaluate("document.getElementById('agentFinalCard').dataset.completed==='true'");
                    const duplicate=await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}+'/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preview_id:${JSON.stringify(preview)},accept_incomplete:true})}).then(r=>r.status)`);
                    item.duplicate_status=duplicate;assert.equal(duplicate,409);
                    const s=JSON.parse(await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}).then(r=>r.text())`));
                    item.rawAfter=await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}).then(r=>r.text())`);
                    if(s.task.status==='completed'){
                        const p=s.results.filter(r=>r.tool==='plan_package').at(-1).data.plan;
                        for(const selected of p.selected_files){
                            assert.equal(path.dirname(selected.target),p.destination);
                            const bytes=await readFile(selected.target),source=await readFile(selected.source.path);
                            item.copies.push({source:selected.source.path,target:selected.target,sha256:hash(bytes),approved_sha256:selected.snapshot.sha256,source_sha256:hash(source)});
                            assert.equal(hash(bytes),selected.snapshot.sha256);assert.equal(hash(source),originalHash);
                        }
                        const reportBytes=await readFile(p.report.path);item.report_sha256=hash(reportBytes);assert.equal(item.report_sha256,p.report.sha256);
                        item.package_path=p.destination;item.status='controlled_real_execution_passed';
                        assert.equal(item.ui_success,true);
                    }else{
                        assert.equal(item.ui_success,false);
                        item.status=name==='reject'?'rejection_passed':name==='changed'||name==='occupied'?'safety_rejection_observed':name==='partial_source_changed'?'partial_failure_observed':'execution_failed';
                        item.error=s.error;
                        item.failed_report_status=await evaluate(`fetch('/api/agent/tasks/'+${JSON.stringify(state.id)}+'/report').then(r=>r.status)`);
                        assert.equal(item.failed_report_status,409);
                        if(name==='reject'||name==='changed')assert.equal((await readdir(workspace)).some(n=>n.startsWith('package_')),false);
                        if(name==='occupied')assert.equal((await readFile(path.join(destination,'occupied-sentinel.txt'),'utf8')),'must not overwrite');
                        if(name==='partial_source_changed'){
                            const children=s.package_execution.operation_results.map(link=>s.results[link.result_index]);
                            assert.ok(children.some(r=>r.tool==='copy_file'&&r.success===true));
                            assert.ok(children.some(r=>r.tool==='copy_file'&&r.success===false));
                            item.operation_results=s.package_execution.operation_results;item.cleanup_results=s.package_execution.cleanup_results;
                            assert.equal(await evaluate("agentPackagePreview.innerText.includes('文件验证：通过')"),false);
                            const bytes=await readFile(selected[0].target);item.copies.push({source:selected[0].source,target:selected[0].target,sha256:hash(bytes)});
                            assert.equal(hash(bytes),originalHash);
                        }
                    }
                }
            }else{
                assert.equal(await evaluate('approveAgent.disabled'),true);
                if(state.status==='failed')assert.equal(await evaluate('agentState.report'),null);
                assert.equal((await readdir(workspace)).some(n=>n.startsWith('package_')),false);
            }
            item.source_unchanged=hash(await readFile(path.join(workspace,'报名表.txt')))===originalHash;
            if(name!=='changed')assert.equal(item.source_unchanged,true);
            if(await evaluate('agentState.busy'))await evaluate('agentState.busy=false');
        }
        await evaluate("switchAgentWorkflow('organization');runAgent();decideAgent(true)");
        assert.equal(await evaluate('organizationScan.disabled&&organizationExecute.disabled&&approveAgent.disabled'),true);
        assert.deepEqual(pageErrors,[]);
        evidence.status=evidence.cases.every(c=>c.status!=='blocked'&&c.status!=='execution_failed')?'controlled_observations_completed':'blocked';

        console.log(JSON.stringify({status:evidence.status,e2e:false,cases:evidence.cases.map(({name,status,error})=>({name,status,error})),evidence:path.join(manifest.directory,'browser-evidence.json')}));
    }catch(error){evidence.observer_error=error.message;throw error;}finally{
        for(const observer of observers)if(observer.exitCode===null)observer.kill();
        try{await writeFile(path.join(manifest.directory,'browser-evidence.json'),JSON.stringify(evidence,null,2),{flag:'wx'});}finally{
        if(ws)ws.close();browser.kill();await new Promise(resolve=>browser.exitCode!==null?resolve():browser.once('exit',resolve));
        if(path.dirname(profile)===tmpdir()&&path.basename(profile).startsWith('package-fixture-browser-'))await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
        }
    }
});
