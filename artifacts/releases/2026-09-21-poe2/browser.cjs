const fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto')
const {chromium}=require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const root='/var/lib/chickenbro/releases/poe2-20260921',origin='https://www.chickenbro.cloud'
;(async()=>{
 const s=JSON.parse(fs.readFileSync(root+'/private-smoke-sessions.json')).A
 const browser=await chromium.launch({headless:true,executablePath:'/opt/chickenbro-candidates/poe2-20260918/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']})
 try{
 const context=await browser.newContext({viewport:{width:1440,height:1000},permissions:['clipboard-read','clipboard-write']})
 await context.addCookies([{name:'__Host-chickenbro-session',value:s.token,url:origin,secure:true,httpOnly:true,sameSite:'Lax'},{name:'__Host-chickenbro-csrf',value:s.csrf,url:origin,secure:true,sameSite:'Lax'}])
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(90000)
 await page.goto(origin+'/poe2',{waitUntil:'domcontentloaded'})
 await page.getByRole('region',{name:'已解析角色'}).waitFor()
 await page.getByRole('button',{name:'复制 ID',exact:true}).click()
 assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),await page.getByRole('region',{name:'已解析角色'}).locator('code').innerText())
 await page.waitForFunction(()=>document.querySelector('[data-tree-nodes]')?.getAttribute('data-art-ready')==='true')
 await page.screenshot({path:root+'/desktop.png'})
 await page.getByRole('button',{name:'＋ 导入新构筑',exact:true}).click()
 await page.getByRole('textbox',{name:'构筑分享码',exact:true}).fill(JSON.parse(fs.readFileSync(root+'/private-build-code.json')).code)
 await page.getByRole('button',{name:'导入构筑',exact:true}).click()
 const card=page.getByRole('region',{name:'已解析角色'});await card.waitFor()
 const id=await card.locator('code').innerText()
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));await page.screenshot({path:root+'/mobile.png'})
 await page.setViewportSize({width:1440,height:1000});await page.getByRole('button',{name:'删除构筑：我的 POE2 构筑',exact:true}).click();await page.getByRole('button',{name:'确认删除',exact:true}).click()
 await page.waitForFunction(value=>!document.querySelector('[aria-label="已解析角色"]')?.textContent.includes(value),id)
 await page.reload({waitUntil:'domcontentloaded'});await card.waitFor();assert.notEqual(await card.locator('code').innerText(),id)
 const m=JSON.parse(fs.readFileSync(root+'/manifest.json'));let count=0
 for(const [name,sha] of Object.entries(m.webFiles)){const r=await context.request.get(origin+'/'+name);assert.equal(r.status(),200);assert.equal(crypto.createHash('sha256').update(await r.body()).digest('hex'),sha);count++}
 assert.deepEqual(errors,[])
 const result={passed:true,publicFilesMatched:count,realWebImport:true,treeAtlasReady:true,clipboard:true,deletePersists:true,mobileNoOverflow:true,errors}
 fs.writeFileSync(root+'/browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result))
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)})
