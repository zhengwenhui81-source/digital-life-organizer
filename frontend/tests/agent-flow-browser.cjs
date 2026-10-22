/* Isolated visual regression; synthetic snapshots, no Agent/model requests. */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
for(const width of [1440,390])test(`Flow colors, current node and evidence animation at ${width}px`,{timeout:30000},async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-background-networking']});
 try{const page=await browser.newPage({viewport:{width,height:1080}});let requests=0;await page.route('**/*',r=>{requests++;return r.abort();});
 await page.setContent('<style>'+await fs.readFile(path.join(__dirname,'../agent-flow-visualization.css'),'utf8')+'\n'+await fs.readFile(path.join(__dirname,'../agent-workbench.css'),'utf8')+'</style><main id="flow"></main>');
 await page.addScriptTag({content:await fs.readFile(path.join(__dirname,'../agent-flow-visualization.js'),'utf8')});
 for(const status of ['planning','awaiting_clarification','awaiting_approval','failed']){
 const observed=await page.evaluate(status=>{const s={task:{task_id:'visual-test',status},plan:null,results:[],error:status==='failed'?'Planner model request failed':null};document.getElementById('flow').innerHTML=AgentFlowVisualization.render(s,'real');const current=document.querySelector('[data-current="true"]');return {current:current?.dataset.stage,status:current?.dataset.status,border:getComputedStyle(current).borderColor,background:getComputedStyle(current).backgroundColor,label:current.innerText,particles:[...document.querySelectorAll('.agent-flow-arrow')].map(n=>({animation:getComputedStyle(n,'::before').animationName,opacity:getComputedStyle(n,'::before').opacity})),plan:document.querySelector('[data-stage="plan"]').dataset.status,completed:document.querySelectorAll('[data-status="completed"]').length,overflow:document.documentElement.scrollWidth>innerWidth};},status);
 assert.equal(observed.completed,0);assert.equal(observed.overflow,false);
 if(status==='planning'){assert.equal(observed.current,'plan');assert.equal(observed.status,'running');assert.ok(observed.particles.some(p=>p.animation!=='none'));}
 else{assert.ok(observed.particles.every(p=>p.animation==='none'&&p.opacity==='0'));}
 if(status==='awaiting_clarification'){assert.equal(observed.status,'awaiting_clarification');assert.equal(observed.plan,'pending');assert.match(observed.border,/243, 156, 18/);}
 if(status==='awaiting_approval')assert.equal(observed.current,'approve');
 if(status==='failed'){assert.equal(observed.current,'plan');assert.equal(observed.status,'failed');assert.equal(observed.background,'rgb(242, 251, 246)');assert.match(observed.label,/失败/);}
 }
 await page.locator('.agent-flow-details summary').first().click();assert.equal(await page.locator('.agent-flow-details').first().getAttribute('open'),'');
 assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(243, 247, 252)');
 assert.equal(requests,0);
 }finally{await browser.close();}
});
