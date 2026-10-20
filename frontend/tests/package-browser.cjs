/* Installed Chrome + built-in Node CDP client; no dependency installation or HTTP server. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {mkdtemp,rm}=require('node:fs/promises');
const {tmpdir}=require('node:os');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
test('Package Fixture browser: scenarios, confirmation, disabled approval, escaping, narrow layout, no HTTP',{timeout:60000},async()=>{
    const profile=await mkdtemp(path.join(tmpdir(),'package-fixture-browser-'));
    const browser=spawn(process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--disable-component-update','--disable-sync','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
    let ws;
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
        // Block all HTTP(S) traffic from the fixture target, including accidental future code.
        await call('Network.setBlockedURLs',{urls:['http://*','https://*']});
        const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
        await call('Page.navigate',{url:pathToFileURL(path.resolve(__dirname,'../package-preview.html')).href});
        await evaluate("new Promise(resolve=>{if(document.readyState==='complete')resolve();else addEventListener('load',resolve,{once:true})})");
        for(const width of [1366,390]){
            await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
            const names=await evaluate('PackageFixtures.names');
            for(const name of names){
                const result=await evaluate(`(()=>{scenario.value=${JSON.stringify(name)};scenario.dispatchEvent(new Event('change'));return {disabled:formalApprove.disabled,overflow:document.documentElement.scrollWidth>innerWidth,text:document.body.innerText}})()`);
                assert.equal(result.disabled,true);assert.equal(result.overflow,false,name+' at '+width);assert.match(result.text,/Mock \/ Fixture/);
                assert.match(result.text,/材料真实性、完整性及有效性未由本界面核验/);
                if(['executing','verifying'].includes(name)){assert.match(result.text,/Package 执行中/);assert.match(result.text,/尚无完成结果/);assert.doesNotMatch(result.text,/Package 执行与文件验证成功/);}
                if(name==='success')assert.match(result.text,/Package 执行与文件验证成功/);
                if(name==='verification_failed'){assert.match(result.text,/验证失败，Package 未成功/);assert.doesNotMatch(result.text,/文件验证：通过/);}
                if(name==='cleanup_succeeded'){assert.match(result.text,/清理成功 · 仅失败复制片段已移除/);assert.doesNotMatch(result.text,/Package 执行与文件验证成功/);}
            }
        }
        const combinations=await evaluate(`(()=>{
            const findings=[];
            for(const kind of ['null_task','null_operation','unresolved_source','failed_report','missing_targets','missing_cleanup','workspace_mismatch','unsafe_timestamp']){
                const d=PackageFixtures.get(kind==='null_operation'?'stale_success':kind==='unresolved_source'?'risks':'success');
                if(kind==='null_task')d.planResult.data.plan.task=null;
                if(kind==='null_operation')d.planResult.data.plan.operations[0]=null;
                if(kind==='unresolved_source'){d.planResult.data.plan.unresolved[0].source_result_index=999;riskIntent.checked=true;riskIntent.dispatchEvent(new Event('change'));}
                if(kind==='failed_report')d.report.status='failed';
                if(kind==='missing_targets')delete d.planResult.data.plan.verification_targets;
                if(kind==='missing_cleanup')delete d.snapshot.package_execution.cleanup_results;
                if(kind==='workspace_mismatch')d.snapshot.task.workspace='E:\\\\other';
                if(kind==='unsafe_timestamp')d.planResult.data.plan.selected_files[0].snapshot.mtime_ns=1792310400000000000;
                const before=JSON.stringify(d);content.innerHTML=PackagePreview.render(d);
                findings.push({kind,text:content.innerText,unchanged:before===JSON.stringify(d),disabled:formalApprove.disabled,overflow:document.documentElement.scrollWidth>innerWidth});
            }
            return findings;
        })()`);
        const warnings={null_task:/方案数据不完整/,null_operation:/执行记录不完整\/无效/,unresolved_source:/未决事项来源关联无效/,failed_report:/Package 报告状态无效/,missing_targets:/verification_targets 缺失或无效/,missing_cleanup:/cleanup_results 缺失或无效/,workspace_mismatch:/任务上下文不一致/,unsafe_timestamp:/精度无法确认/};
        for(const item of combinations){assert.equal(item.unchanged,true);assert.equal(item.disabled,true);assert.equal(item.overflow,false);assert.match(item.text,warnings[item.kind]);assert.match(item.text,/文件验证：未确认通过/);assert.doesNotMatch(item.text,/文件验证：通过/);}
        const failedChains=await evaluate(`(()=>{
            return [5,6].map(index=>{
                const d=PackageFixtures.get('success');d.snapshot.task.status='failed';d.report=null;
                d.snapshot.results[index]={tool:index===5?'create_folder':'copy_file',success:false,data:null,message:'injected failure',error:'original failure retained'};
                const before=JSON.stringify(d),m=PackagePreview.inspect(d);content.innerHTML=PackagePreview.render(d);
                return {index,bound:m.boundOperations.map(row=>row.result_index),writes:m.writes.filter(row=>row.result.success).length,
                    verification:m.verification,build:m.build,packageSucceeded:m.packageSucceeded,
                    anomalous:m.anomalousResults.map(row=>row.result_index),rows:m.operationRows.map(row=>({valid:row.evidenceValid,label:row.label})),
                    text:content.innerText,disabled:formalApprove.disabled,unchanged:before===JSON.stringify(d),overflow:document.documentElement.scrollWidth>innerWidth};
            });
        })()`);
        for(const item of failedChains){
            assert.deepEqual(item.bound,item.index===5?[5]:[5,6]);assert.equal(item.writes,item.index===5?0:1);
            assert.equal(item.verification,null);assert.equal(item.build,null);assert.equal(item.packageSucceeded,false);
            assert.deepEqual(item.anomalous,item.index===5?[6,7,8,9]:[7,8,9]);
            assert.ok(item.rows.slice(item.index-4).every(row=>!row.valid&&row.label==='失败后异常记录，不可作为有效执行证据'));
            assert.match(item.text,/original failure retained/);assert.match(item.text,/失败后异常记录/);
            if(item.index===5)assert.doesNotMatch(item.text,/文件操作执行成功/);
            assert.doesNotMatch(item.text,/文件验证：通过|Package 执行与文件验证成功/);
            assert.equal(item.disabled,true);assert.equal(item.unchanged,true);assert.equal(item.overflow,false);
        }
        const reportCases=await evaluate(`(()=>{
            return ['new_verify_failure','foreign_found','foreign_versions','unrun_conflicts','missing_conflict_risk'].map(kind=>{
                const d=PackageFixtures.get('success'),p=d.planResult.data.plan;
                if(kind==='new_verify_failure'){
                    const bad=structuredClone(d.snapshot.results[8]);bad.data.passed=false;bad.data.checks[0].passed=false;
                    d.snapshot.results.splice(9,0,bad);d.snapshot.package_execution.final_result_index=10;
                }
                if(kind==='foreign_found')d.report.found_files=[{path:'OLD_FOREIGN_SOURCE'}];
                if(kind==='foreign_versions')d.report.version_groups=[{group_id:'FOREIGN_OLD_GROUP'}];
                if(kind==='unrun_conflicts'||kind==='missing_conflict_risk'){
                    p.analysis.detect_conflicts=null;
                    p.unresolved=p.unresolved.filter(u=>u.source_tool!=='detect_conflicts');
                    if(kind==='unrun_conflicts')p.unresolved.push({kind:'analysis_not_run',source_tool:'detect_conflicts',source_result_index:null,documents:[],text:'Conflict analysis not run'});
                    d.report.package_unresolved.items=structuredClone(p.unresolved);d.report.conflicts=[];
                    d.snapshot.results[2]={tool:'read_document',success:true,data:{},message:'no conflict analysis',error:null};
                    d.snapshot.results[4]=structuredClone(d.planResult);
                }
                const before=JSON.stringify(d),m=PackagePreview.inspect(d);content.innerHTML=PackagePreview.render(d);
                return {kind,verified:m.verification!==null,build:m.build!==null,bound:m.boundOperations.length,
                    packageSucceeded:m.packageSucceeded,authorization:m.authorizationConfirmed,text:content.innerText,
                    disabled:formalApprove.disabled,unchanged:before===JSON.stringify(d),overflow:document.documentElement.scrollWidth>innerWidth};
            });
        })()`);
        for(const item of reportCases){
            assert.equal(item.packageSucceeded,item.kind==='unrun_conflicts');
            assert.equal(item.authorization,false);assert.equal(item.disabled,true);assert.equal(item.unchanged,true);assert.equal(item.overflow,false);
            if(item.kind==='new_verify_failure'){assert.equal(item.verified,false);assert.equal(item.build,false);assert.equal(item.bound,3);assert.doesNotMatch(item.text,/文件验证：通过/);}
            if(item.kind==='unrun_conflicts'){assert.equal(item.bound,4);assert.match(item.text,/Conflict analysis not run/);assert.match(item.text,/打包执行成功，但材料包仍有缺项或未决事项/);}
            else {assert.match(item.text,/报告未通过当前执行完整性检查/);assert.doesNotMatch(item.text,/Package 执行与文件验证成功/);}
        }

        const snapshotGates=await evaluate(`(()=>{
            return ['missing_snapshot','stale_before_plan','failed','unavailable'].map(kind=>{
                const s=PackageFixtures.get('complete').snapshot;
                s.preview_id='server-preview';s.pending_operations=[{tool:'build_package',step_id:'build',arguments:{}}];
                const file=s.results[4].data.plan.selected_files[0];
                const hidden=[file.source.filename,file.source.path,file.target];
                if(kind==='missing_snapshot')delete file.snapshot;
                if(kind==='stale_before_plan')s.results.splice(4,0,structuredClone(s.results[3]));
                if(kind==='failed'){s.task.status='failed';s.error='current task failed';}
                if(kind==='unavailable')s.results=[];
                const before=JSON.stringify(s);content.innerHTML=PackagePreview.renderSnapshot(s);
                return {kind,text:content.innerText,leaks:hidden.some(value=>content.innerText.includes(value)),unchanged:before===JSON.stringify(s),disabled:formalApprove.disabled,overflow:document.documentElement.scrollWidth>innerWidth};
            });
        })()`);
        for(const gate of snapshotGates){
            assert.equal(gate.leaks,false);assert.equal(gate.unchanged,true);assert.equal(gate.disabled,true);assert.equal(gate.overflow,false);
            assert.doesNotMatch(gate.text,/提议文件|具体文件映射|文件验证：通过/);
            assert.match(gate.text,gate.kind==='missing_snapshot'?/快照数据不完整/:gate.kind==='stale_before_plan'?/来源不一致或已过期/:gate.kind==='failed'?/当前失败/:/规划数据尚未提供/);
        }
        const integrated=await evaluate(`(()=>{
            return ['executing','verifying','new_verification'].map(kind=>{
                const s=PackageFixtures.get(kind==='new_verification'?'success':kind).snapshot;
                if(kind==='new_verification'){
                    const bad=structuredClone(s.results[8]);bad.data.passed=false;bad.data.checks[0].passed=false;
                    s.results.splice(9,0,bad);s.package_execution.final_result_index=10;
                }
                const before=JSON.stringify(s),m=PackagePreview.inspectSnapshot(s);content.innerHTML=PackagePreview.renderSnapshot(s);
                return {kind,state:m.state,text:content.innerText,unchanged:before===JSON.stringify(s),disabled:formalApprove.disabled,overflow:document.documentElement.scrollWidth>innerWidth};
            });
        })()`);
        for(const item of integrated){
            assert.equal(item.state,item.kind==='new_verification'?'invalid':'provided');
            if(item.kind==='new_verification'){assert.match(item.text,/验证记录缺失、重复或关联不完整/);assert.doesNotMatch(item.text,/结题报告.txt|具体文件映射|文件验证：通过/);}
            else{assert.match(item.text,/Package 执行中/);assert.match(item.text,/结题报告.txt/);}
            assert.doesNotMatch(item.text,/Package 执行与文件验证成功/);
            assert.equal(item.unchanged,true);assert.equal(item.disabled,true);assert.equal(item.overflow,false);
        }
        // The unavailable gate intentionally has no details/pre; restore a valid
        // Fixture before running the existing detailed-layout assertion.
        await evaluate("scenario.value='complete';scenario.dispatchEvent(new Event('change'))");
        assert.equal(await evaluate("getComputedStyle(document.querySelector('pre')).whiteSpace==='pre-wrap'"),true);
        assert.equal(await evaluate("(()=>{scenario.value='risks';scenario.dispatchEvent(new Event('change'));riskIntent.click();return PackageDemo.state.accepted})()"),true);
        assert.equal(await evaluate("(()=>{scenario.value='complete';scenario.dispatchEvent(new Event('change'));return riskIntent.checked||PackageDemo.state.accepted})()"),false);
        assert.equal(await evaluate("(()=>{const d=PackageFixtures.get();d.planResult.data.plan.report.content='<img src=x onerror=\"window.pwned=true\">';content.innerHTML=PackagePreview.render(d);return content.querySelectorAll('img').length})()"),0);
        assert.equal(await evaluate('formalApprove.disabled'),true);
        assert.deepEqual(pageErrors,[]);
        assert.deepEqual(network.filter(r=>/^https?:/.test(r.url)),[]);
        console.log('Validated 22 fixtures × 2 viewports + 8 malformed-input combinations + 2 failed execution chains + 5 verification/report cases + 4 Snapshot detail gates + 3 integrated Snapshot states; no HTTP requests; approval disabled.');
    }finally{
        if(ws)ws.close();browser.kill();await new Promise(resolve=>browser.exitCode!==null?resolve():browser.once('exit',resolve));
        // Only remove the exact profile created by this test, outside user Workspace.
        if(path.dirname(profile)===tmpdir()&&path.basename(profile).startsWith('package-fixture-browser-'))await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
    }
});
