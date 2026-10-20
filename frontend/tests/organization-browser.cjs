/* Installed Chrome + Node CDP. Static localhost assets only; no Agent backend. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {mkdtemp,rm,readFile}=require('node:fs/promises');
const {tmpdir}=require('node:os');
const path=require('node:path');
const {createServer}=require('node:http');

test('Organization formal shell and isolated Fixture browser regression',{timeout:60000},async()=>{
    const files=new Set(['agent-api.js','agent-mock.js','agent-results.js','package-preview.js','organization-preview.js','organization-demo.js']);
    const api=[];
    const server=createServer(async(req,res)=>{
        try{
            const name=req.url==='/'?'index.html':req.url.startsWith('/static/')?req.url.slice(8):null;
            if(req.url.startsWith('/api/')){
                api.push({url:req.url,method:req.method});
                const allowed=req.method==='GET'&&req.url==='/api/sessions';
                res.writeHead(allowed?200:409,{'Content-Type':'application/json'});res.end(JSON.stringify(allowed?{sessions:[]}:{detail:'No backend in static test'}));return;
            }
            if(name!=='index.html'&&!files.has(name)){res.writeHead(404);res.end();return;}
            const body=await readFile(path.resolve(__dirname,'..',name));
            res.writeHead(200,{'Content-Type':name.endsWith('.js')?'text/javascript':'text/html; charset=utf-8'});res.end(body);
        }catch(error){res.writeHead(500);res.end('Static test asset unavailable');}
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const url='http://127.0.0.1:'+server.address().port;
    const profile=await mkdtemp(path.join(tmpdir(),'organization-browser-'));
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
        // External assets are blocked; only the test's static localhost server is needed.
        await call('Network.setBlockedURLs',{urls:['https://*']});
        const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
        await call('Page.navigate',{url});
        await evaluate("new Promise(resolve=>{if(document.readyState==='complete')resolve();else addEventListener('load',resolve,{once:true})})");
        for(const width of [1366,390]){
            await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
            const initial=await evaluate(`(()=>{
                switchAgentWorkflow('organization');
                return {text:organizationRealPreview.innerText,inputVisible:!!agentWorkspacePath.getClientRects().length&&!!agentGoal.getClientRects().length,
                    demoHidden:organizationDemoPanel.hidden,run:document.getElementById('runAgent').disabled,scan:organizationScan.disabled,execute:organizationExecute.disabled};
            })()`);
            assert.match(initial.text,/分类接口待团队确认/);assert.equal(initial.inputVisible,true);assert.equal(initial.demoHidden,true);
            assert.equal(initial.run,true);assert.equal(initial.scan,true);assert.equal(initial.execute,true);
            await evaluate('runAgent();pollAgent();decideAgent(true);decideAgent(false)');
            for(const kind of ['invalid','foreign','stale','package']){
                const result=await evaluate(`(()=>{
                    const expected={task_id:'current',user_goal:'organize',workspace:'E:/synthetic'};
                    const s={task:{...expected,status:'completed'},results:[{tool:'unconfirmed',success:true,data:{source:'PRIVATE_MAPPING',target:'PRIVATE_TARGET'},message:'opaque',error:null}]};
                    if(${JSON.stringify(kind)}==='invalid')s.results=[null];
                    if(${JSON.stringify(kind)}==='foreign')s.task.task_id='FOREIGN';
                    if(${JSON.stringify(kind)}==='stale')s.results.push(s.results[0]);
                    if(${JSON.stringify(kind)}==='package')s.results[0].tool='plan_package';
                    const before=JSON.stringify(s);renderOrganizationStatus(s,expected);
                    return {text:organizationRealPreview.innerText,unchanged:before===JSON.stringify(s)};
                })()`);
                assert.doesNotMatch(result.text,/PRIVATE_|FOREIGN|文件验证：通过/);assert.equal(result.unchanged,true);
            }
            await evaluate('setOrganizationDemo(true)');
            for(const scenario of ['mixed','single','empty','unknown','collision','incomplete']){
                const result=await evaluate(`(()=>{organizationScenario.value=${JSON.stringify(scenario)};showOrganizationPreview();return {text:organizationPreview.innerText,overflow:document.documentElement.scrollWidth>innerWidth}})()`);
                assert.match(result.text,scenario==='incomplete'?/结构不完整/:/本地 UI 演示预览/);
                if(scenario==='collision')assert.match(result.text,/1 组可能冲突/);
                assert.equal(result.overflow,false,scenario+' at '+width);
            }
            await evaluate("organizationScenario.value='mixed';showOrganizationPreview()");
            assert.equal(await evaluate("(()=>{const d=organizationPreview.querySelector('details');d.open=false;return d.open})()"),false);
            assert.equal(await evaluate("(()=>{const d=organizationPreview.querySelector('details');d.open=true;return d.open})()"),true);
            assert.equal(await evaluate(`(()=>{const d=OrganizationDemo.get('single');d.categories[0].name='<img src=x onerror="window.pwned=true">';d.categories[0].files[0].source='E:/'+ 'long-path/'.repeat(90);organizationPreview.innerHTML=OrganizationPreview.render(d);return organizationPreview.querySelectorAll('img').length})()`),0);
            assert.equal(await evaluate('!!window.pwned'),false);
            assert.equal(await evaluate('document.documentElement.scrollWidth>innerWidth'),false);
            await evaluate('setOrganizationDemo(false)');
            assert.match(await evaluate('organizationRealPreview.innerText'),/真实分类数据尚未接入/);
            assert.equal(await evaluate('organizationDemoPanel.hidden'),true);
            await evaluate("switchAgentWorkflow('materials')");
        }
        // Ordinary material Mock approval/report remain functional after workflow changes.
        const status=await evaluate(`(async()=>{
            agentMode.value='mock';agentMode.dispatchEvent(new Event('change'));agentWorkspacePath.value='E:/synthetic';agentGoal.value='synthetic goal';
            await runAgent();for(let i=0;i<5;i++)await pollAgent();const awaiting=agentState.task.status;
            await decideAgent(true);for(let i=0;i<3;i++)await pollAgent();return {awaiting,final:agentState.task.status,report:!!agentState.report};
        })()`);
        assert.equal(status.awaiting,'awaiting_approval');assert.equal(status.final,'completed');assert.equal(status.report,true);
        assert.deepEqual(pageErrors,[]);
        assert.ok(api.every(r=>r.method==='GET'&&r.url==='/api/sessions'),JSON.stringify(api));
        assert.equal(network.some(r=>/\/api\/agent\//.test(r.url)),false);
        console.log('Validated formal blocked shell, six isolated Fixtures at 1366/390, malformed/foreign/stale/Package payloads, XSS/long paths, no Agent requests, material Mock completion.');
    }finally{
        if(ws)ws.close();browser.kill();await new Promise(resolve=>browser.exitCode!==null?resolve():browser.once('exit',resolve));
        await new Promise(resolve=>server.close(resolve));
        if(path.dirname(profile)===tmpdir()&&path.basename(profile).startsWith('organization-browser-'))await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
    }
});
