/* Optional Chrome check against demo/run_offline_browser.py --no-browser.
 * Uses installed Playwright/Chrome via env; never stubs Agent HTTP responses. */
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
(async()=>{
    const baseURL=process.env.UI_BASE_URL;
    if(!baseURL || new URL(baseURL).hostname!=='127.0.0.1')throw Error('Set UI_BASE_URL to the actual 127.0.0.1 URL printed by the offline harness; there is no default port.');
    const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
    try {
        for(const [width,height] of [[1280,720],[1366,768]]){
            const page=await browser.newPage({viewport:{width,height}}), errors=[], external=[], mutations=[];
            page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
            await page.route('**/*',route=>{
                if(new URL(route.request().url()).hostname!=='127.0.0.1'){external.push(route.request().url());return route.abort();}
                return route.continue();
            });
            page.on('request',r=>{if(r.method()==='POST')mutations.push(new URL(r.url()).pathname);});
            await page.goto(baseURL,{waitUntil:'domcontentloaded'});
            await page.waitForSelector('#offlineBanner');assert.match(await page.locator('#offlineBanner').innerText(),/固定 Planner · 非 LLM/);
            assert.equal(await page.locator('#agentMode').inputValue(),'real');assert.equal(await page.locator('#agentMode').isDisabled(),true);
            for(const scenario of ['mixed','no_candidates','no_requirements','read_failure','empty']){
                await page.selectOption('#offlineScenario',scenario);
                await page.locator('#runAgent').click();
                await page.waitForFunction(()=>agentState.task && ['completed','failed'].includes(agentState.task.status) && !agentState.pollInFlight,{},{timeout:20000});
                const failed=['read_failure','empty'].includes(scenario);
                assert.equal(await page.evaluate(()=>agentState.task.status),failed?'failed':'completed');
                const html=await page.locator('#agentMatching').innerText();
                if(failed){assert.match(html,/未执行/);assert.equal(await page.locator('#agentError').isVisible(),true);}
                else if(scenario==='no_requirements')assert.match(html,/没有明确的材料要求/);
                else if(scenario==='no_candidates')assert.match(html,/3 项本次未找到文件名候选/);
                else {assert.match(html,/1 个文件名候选/);assert.match(html,/2 个文件名候选/);assert.match(html,/file_/);assert.match(html,/尚未审核/);}
                assert.equal(await page.locator('#approveAgent').isDisabled(),true);
                assert.equal(await page.locator('#copyPackagePath').isVisible(),false);
                assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
                assert.equal(await page.evaluate(()=>{
                    const title=document.querySelector('#offlineBanner strong'),r=title.getBoundingClientRect();
                    return r.top>=0 && document.elementFromPoint(r.left+5,r.top+5)===title;
                }),true);
                if(scenario==='mixed' && process.env.UI_SCREENSHOT_DIR){
                    await page.locator('#agentMatching').scrollIntoViewIfNeeded();
                    await page.screenshot({path:process.env.UI_SCREENSHOT_DIR+`/offline-matching-${width}x${height}.png`});
                }
            }
            assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
            assert.equal(mutations.length,5);assert.ok(mutations.every(p=>p==='/api/agent/tasks'));
            await page.close();console.log(`PASS ${width}x${height}: five real HTTP scenarios, visible offline label, no external requests/errors/write requests`);
        }
    }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
