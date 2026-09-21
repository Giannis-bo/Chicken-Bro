// Run only on the authorized cloud Candidate. Never log codes or session values.
const {chromium}=require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs=require('node:fs'),assert=require('node:assert/strict')
const root='/opt/chickenbro-candidates/poe2-20260918',origin='https://www.chickenbro.cloud',out=root+'/evidence/pob-only'
async function main(){
 const session=JSON.parse(fs.readFileSync(root+'/runtime/browser/session-fixtures.json','utf8')).A
 const browser=await chromium.launch({headless:true,executablePath:root+'/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']})
 const context=await browser.newContext({viewport:{width:1440,height:1000}})
 await context.addCookies([{name:'__Host-chickenbro-poe2-candidate-session',value:session.token,url:origin,httpOnly:true,secure:true,sameSite:'Lax'},{name:'__Host-chickenbro-poe2-candidate-csrf',value:session.csrf,url:origin,secure:true,sameSite:'Lax'}])
 const page=await context.newPage(),errors=[],checks=[]
 page.on('pageerror',()=>errors.push('pageerror'))
 try {
  await page.goto(origin+'/poe2-candidate/poe2',{waitUntil:'domcontentloaded'})
  const field=page.getByLabel('构筑分享码',{exact:true}),button=page.getByRole('button',{name:'导入构筑',exact:true})
  await field.waitFor()
  assert.equal(await page.getByRole('button',{name:/国服 · WeGame|国际服 · poe.ninja|使用示例构筑|读取角色/}).count(),0)
  assert.equal(await page.locator('input[type=file]').count(),0)
  assert.ok(await page.getByText(/IMPORT CODE FOR PATH OF BUILDING/).isVisible())
  assert.ok(await page.locator('a[href="https://poe.ninja/poe2/builds"]').count()>0)
  assert.ok(await page.locator('a[href*="github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2"]').count()>0)
  let importPosts=0
  page.on('request',req=>{if(req.method()==='POST'&&new URL(req.url()).pathname.endsWith('/poe2/builds'))importPosts++})
  for(const bad of ['', 'https://poe.ninja/poe2/profile/a/b/character/c','<PathOfBuilding2><Build /></PathOfBuilding2>']){await field.fill(bad);await button.click();await page.getByRole('alert').waitFor();assert.ok((await page.getByRole('alert').innerText()).includes('字符串'))}
  assert.equal(importPosts,0)
  checks.push('single code entry, copy instructions, official links, URL/XML/empty rejected')
  await field.fill(fs.readFileSync(root+'/evidence/link-research/user-ninja-code-20260920.txt','utf8').trim())
  await button.click()
  await page.getByRole('heading',{name:'角色解析成功',exact:true}).waitFor({timeout:90000})
  const card=page.getByRole('region',{name:'已解析角色',exact:true})
  const text=await card.innerText()
  assert.ok(text.includes('96'));assert.ok(text.includes('Mercenary'));assert.ok(text.includes('Gemling Legionnaire'))
  assert.equal(await page.getByRole('heading',{name:'第二步 · 调整与对比',exact:true}).count(),0)
  checks.push('actual supplied code parsed; level96 Mercenary Gemling Legionnaire; remains on step1')
  await page.screenshot({path:out+'/parsed-desktop.png',fullPage:true,mask:[page.locator('textarea')]})
  await page.setViewportSize({width:390,height:844})
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+4))
  await page.screenshot({path:out+'/parsed-mobile.png',fullPage:true,mask:[page.locator('textarea')]})
  await page.getByRole('button',{name:'继续调整与对比',exact:true}).click()
  await page.getByRole('heading',{name:'第二步 · 调整与对比',exact:true}).waitFor()
  await page.getByRole('button',{name:'＋ 导入新构筑',exact:true}).click()
  await field.waitFor();assert.equal(await field.inputValue(),'')
  assert.equal(await page.getByRole('heading',{name:'角色解析成功',exact:true}).count(),0)
  checks.push('390px no overflow; explicit continue; next import clears success card')
  assert.deepEqual(errors,[])
  fs.writeFileSync(out+'/browser.json',JSON.stringify({passed:true,checks,errors,summary:{level:96,className:'Mercenary',ascendancy:'Gemling Legionnaire'},screenshots:'textarea masked'},null,2))
  console.log(JSON.stringify({passed:true,checks}))
 }catch(e){console.error('PoB-only browser check failed: '+String(e.message).replace(/https?:\/\/\S+/g,'[URL]'));process.exitCode=1}
 finally {await browser.close()}
}
main().catch(()=>{console.error('PoB-only browser launch failed');process.exitCode=1})
