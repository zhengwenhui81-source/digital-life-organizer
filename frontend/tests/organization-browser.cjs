/* Optional real-browser UI regression; no classification or filesystem API calls.
 * Set PLAYWRIGHT_MODULE and CHROME_PATH to installed local tools, no dependency install.
 * Run existing app on 127.0.0.1:18082 (or set UI_BASE_URL). */
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
(async()=>{
    const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true});
    try {
        for(const [width,height] of [[1280,720],[1366,768]]) {
            const page=await browser.newPage({viewport:{width,height}}), errors=[], requests=[];
            page.on('pageerror',e=>errors.push(e.message));
            page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
            await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:'/* offline browser regression: use system fonts */'}));
            await page.goto(process.env.UI_BASE_URL || 'http://127.0.0.1:18082',{waitUntil:'domcontentloaded'});
            await page.locator('#organizationWorkflowTab').click();
            assert.match(await page.locator('#organizationPreview').innerText(),/尚未开始/);
            page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))requests.push(r.url());});
            const noOverflow=async()=>assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
            for(const scenario of ['mixed','single','empty','unknown','collision','incomplete']) {
                await page.selectOption('#organizationScenario',scenario);await page.locator('#organizationLoad').click();
                const content=await page.locator('#organizationPreview').innerText();
                assert.match(content,scenario==='incomplete'?/数据结构不完整/:/本地 UI 演示预览/);
                if(scenario==='collision')assert.match(content,/1 组可能冲突/);
                await noOverflow();
            }
            await page.selectOption('#organizationScenario','mixed');await page.locator('#organizationLoad').click();
            const folder=page.locator('#organizationPreview details').first();
            assert.equal(await folder.getAttribute('open'),'');await folder.locator(':scope > summary').click();
            assert.equal(await folder.getAttribute('open'),null);await folder.locator(':scope > summary').click();
            assert.equal(await folder.getAttribute('open'),'');
            await page.evaluate(()=>{
                const d=OrganizationDemo.get('single'), bad='<img src=x onerror="window.pwned=true">';
                d.categories[0].name=bad;Object.assign(d.categories[0].files[0],{filename:bad,reason:bad,source:'E:\\'+ '很长的路径'.repeat(90),target:[...Array(12).fill('深层目录'),bad]});
                document.getElementById('organizationPreview').innerHTML=OrganizationPreview.render(d);
            });
            assert.equal(await page.locator('#organizationPreview img').count(),0);
            assert.equal(await page.evaluate(()=>!!window.pwned),false);await noOverflow();
            assert.equal(await page.locator('#organizationWorkspace button:disabled').count(),2);
            await page.selectOption('#organizationScenario','mixed');await page.locator('#organizationLoad').click();
            if(process.env.UI_SCREENSHOT_DIR) {
                await page.screenshot({path:process.env.UI_SCREENSHOT_DIR+`/organization-${width}x${height}.png`});
                await page.locator('#organizationPreview .org-grid').scrollIntoViewIfNeeded();
                await page.screenshot({path:process.env.UI_SCREENSHOT_DIR+`/organization-details-${width}x${height}.png`});
            }
            await page.locator('#organizationReset').click();assert.match(await page.locator('#organizationPreview').innerText(),/尚未开始/);
            assert.deepEqual(requests,[]);
            await page.locator('#materialWorkflowTab').click();assert.equal(await page.locator('#materialWorkspace').isVisible(),true);
            // Existing material mode still works after organization UI interactions.
            await page.selectOption('#agentMode','mock');await page.locator('#agentWorkspacePath').fill('E:\\unknown-workspace');await page.locator('#agentGoal').fill('准备材料');
            await page.evaluate(()=>runAgent());
            for(let i=0;i<5;i++)await page.evaluate(()=>pollAgent());
            assert.equal(await page.evaluate(()=>agentState.task.status),'awaiting_approval');
            await page.evaluate(()=>decideAgent(true));for(let i=0;i<3;i++)await page.evaluate(()=>pollAgent());
            assert.equal(await page.evaluate(()=>agentState.task.status),'completed');
            assert.deepEqual(requests,[]);
            assert.deepEqual(errors,[]);await page.close();
            console.log(`PASS ${width}x${height}: all scenarios, tree, XSS, long paths, no API, material Mock completion, no console/page errors`);
        }
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
