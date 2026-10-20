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
        assert.equal(await evaluate("getComputedStyle(document.querySelector('pre')).whiteSpace==='pre-wrap'"),true);
        assert.equal(await evaluate("(()=>{scenario.value='risks';scenario.dispatchEvent(new Event('change'));riskIntent.click();return PackageDemo.state.accepted})()"),true);
        assert.equal(await evaluate("(()=>{scenario.value='complete';scenario.dispatchEvent(new Event('change'));return riskIntent.checked||PackageDemo.state.accepted})()"),false);
        assert.equal(await evaluate("(()=>{const d=PackageFixtures.get();d.planResult.data.plan.report.content='<img src=x onerror=\"window.pwned=true\">';content.innerHTML=PackagePreview.render(d);return content.querySelectorAll('img').length})()"),0);
        assert.equal(await evaluate('formalApprove.disabled'),true);
        assert.deepEqual(pageErrors,[]);
        assert.deepEqual(network.filter(r=>/^https?:/.test(r.url)),[]);
        console.log('Validated 18 fixtures × 2 viewports + 8 malformed-input combinations; no HTTP requests; approval disabled.');
    }finally{
        if(ws)ws.close();browser.kill();await new Promise(resolve=>browser.exitCode!==null?resolve():browser.once('exit',resolve));
        // Only remove the exact profile created by this test, outside user Workspace.
        if(path.dirname(profile)===tmpdir()&&path.basename(profile).startsWith('package-fixture-browser-'))await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
    }
});
