// Cloud-only: create and delete one verification build; never log sources or cookies.
const {chromium} = require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs = require('node:fs'), assert = require('node:assert/strict'), crypto = require('node:crypto')
const root='/opt/chickenbro-candidates/poe2-20260918', origin='https://www.chickenbro.cloud', prefix=origin+'/poe2-candidate/api/v2/poe2', out=root+'/evidence/build-list'
;(async()=>{
 const sessions=JSON.parse(fs.readFileSync(root+'/runtime/browser/compare-cleanup-sessions.json'))
 const browser=await chromium.launch({headless:true,executablePath:root+'/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']})
 const cookies=row=>[{name:'__Host-chickenbro-poe2-candidate-session',value:row.token,url:origin,httpOnly:true,secure:true,sameSite:'Lax'},{name:'__Host-chickenbro-poe2-candidate-csrf',value:row.csrf,url:origin,secure:true,sameSite:'Lax'}]
 const a=await browser.newContext({viewport:{width:1440,height:1000}}), b=await browser.newContext()
 await a.addCookies(cookies(sessions.A)); await b.addCookies(cookies(sessions.B))
 const headers={'X-CSRF-Token':sessions.A.csrf,Origin:origin}
 try {
  const existing=(await (await a.request.get(prefix+'/builds')).json()).items
  assert.ok(existing.length)
  const source=(await (await a.request.get(prefix+'/builds/'+existing[0].id)).json()).source
  const imported=await a.request.post(prefix+'/builds',{headers,data:{source,title:'删除验证 · 佣兵构筑'},timeout:90000})
  assert.equal(imported.status(),201); const build=await imported.json()
  const denied=await b.request.post(prefix+'/builds/'+build.id+'/delete',{headers:{'X-CSRF-Token':sessions.B.csrf,Origin:origin},data:{}})
  assert.equal(denied.status(),404)
  const csrf=await a.request.post(prefix+'/builds/'+build.id+'/delete',{data:{}}); assert.equal(csrf.status(),403)
  const page=await a.newPage(),errors=[]; page.on('pageerror',e=>errors.push(e.name)); page.setDefaultTimeout(90000)
  await page.goto(origin+'/poe2-candidate/poe2',{waitUntil:'domcontentloaded'})
  const remove=page.getByRole('button',{name:'删除构筑：'+build.title,exact:true})
  await remove.waitFor(); await page.getByRole('region',{name:'已解析角色'}).waitFor()
  await page.locator('aside').first().screenshot({path:out+'/desktop.png'})
  await remove.click(); await page.getByRole('button',{name:'取消',exact:true}).click(); assert.equal(await remove.count(),1)
  await remove.click()
  await page.getByRole('group',{name:'确认删除构筑'}).screenshot({path:out+'/confirm.png'})
  await page.getByRole('button',{name:'确认删除',exact:true}).click(); await remove.waitFor({state:'detached'})
  assert.equal((await a.request.get(prefix+'/builds/'+build.id)).status(),404)
  await page.reload({waitUntil:'domcontentloaded'}); await page.getByRole('region',{name:'已解析角色'}).waitFor()
  assert.equal(await remove.count(),0)
  const after=(await (await a.request.get(prefix+'/builds')).json()).items
  assert.deepEqual(after.map(x=>x.id),existing.map(x=>x.id))
  await page.setViewportSize({width:390,height:844}); assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2))
  await page.screenshot({path:out+'/mobile.png'})
  let files=0; const walk=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(dir+'/'+e.name):[dir+'/'+e.name])
  for(const file of walk(root+'/build-list-web-build')){
   const name=file.slice((root+'/build-list-web-build/').length),r=await a.request.get(origin+'/poe2-candidate/'+name)
   assert.equal(r.status(),200); assert.equal(crypto.createHash('sha256').update(await r.body()).digest('hex'),crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'));files++
  }
  assert.deepEqual(errors,[])
  const result={passed:true,cancelVerified:true,deletePersistsAfterReload:true,otherBuildsPreserved:true,ownerIsolation:true,csrfProtected:true,mobileNoOverflow:true,publicFilesMatched:files}
  fs.writeFileSync(out+'/verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result))
 } finally {await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)})
