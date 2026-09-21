// Cloud-only Candidate verification; no user data mutations.
const {chromium}=require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs=require('node:fs'), assert=require('node:assert/strict'),crypto=require('node:crypto')
const root='/opt/chickenbro-candidates/poe2-20260918',origin='https://www.chickenbro.cloud',out=root+'/evidence/import-guide'
;(async()=>{
 const session=JSON.parse(fs.readFileSync(root+'/runtime/browser/compare-cleanup-sessions.json')).A
 const browser=await chromium.launch({headless:true,executablePath:root+'/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']})
 const context=await browser.newContext({viewport:{width:1440,height:1000},permissions:['clipboard-read','clipboard-write']})
 await context.addCookies([{name:'__Host-chickenbro-poe2-candidate-session',value:session.token,url:origin,httpOnly:true,secure:true,sameSite:'Lax'},{name:'__Host-chickenbro-poe2-candidate-csrf',value:session.csrf,url:origin,secure:true,sameSite:'Lax'}])
 try {
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.name));page.setDefaultTimeout(60000)
 await page.goto(origin+'/poe2-candidate/poe2',{waitUntil:'domcontentloaded'})
 const card=page.getByRole('region',{name:'已解析角色'});await card.waitFor()
 const id=await card.locator('code').innerText();assert.match(id,/^[0-9a-f-]{36}$/)
 await page.getByRole('button',{name:'复制 ID',exact:true}).click()
 assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),id)
 await card.getByRole('status').waitFor();await card.screenshot({path:out+'/character-desktop.png'})
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));await card.screenshot({path:out+'/character-mobile.png'})
 await page.getByRole('button',{name:'＋ 导入新构筑',exact:true}).click()
 const guide=page.getByRole('region',{name:'导入构筑指引'});assert.ok(!(await guide.innerText()).includes('这里只接受'))
 await guide.screenshot({path:out+'/guide-mobile.png'})
 await page.setViewportSize({width:1440,height:1000});await guide.screenshot({path:out+'/guide-desktop.png'})
 let count=0;const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(x=>x.isDirectory()?walk(d+'/'+x.name):[d+'/'+x.name])
 for(const f of walk(root+'/import-guide-web-build')){const r=await context.request.get(origin+'/poe2-candidate/'+f.slice((root+'/import-guide-web-build/').length));assert.equal(r.status(),200);assert.equal(crypto.createHash('sha256').update(await r.body()).digest('hex'),crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex'));count++}
 assert.deepEqual(errors,[]);const result={passed:true,clipboardExactId:true,removedSentence:true,mobileNoOverflow:true,publicFilesMatched:count};fs.writeFileSync(out+'/verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result))
 } finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)})
