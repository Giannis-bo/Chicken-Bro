// Cloud Candidate localization check; uses only an authorized user-supplied code.
const {chromium}=require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs=require('node:fs'),assert=require('node:assert/strict')
const root='/opt/chickenbro-candidates/poe2-20260918',origin='https://www.chickenbro.cloud',out=root+'/evidence/cn-terms'
async function main(){
 const session=JSON.parse(fs.readFileSync(root+'/runtime/browser/session-fixtures.json','utf8')).A
 const browser=await chromium.launch({headless:true,executablePath:root+'/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']})
 const context=await browser.newContext({viewport:{width:1440,height:1000}})
 await context.addCookies([{name:'__Host-chickenbro-poe2-candidate-session',value:session.token,url:origin,httpOnly:true,secure:true},{name:'__Host-chickenbro-poe2-candidate-csrf',value:session.csrf,url:origin,secure:true}])
 const page=await context.newPage(),errors=[]
 page.on('pageerror',()=>errors.push('pageerror'))
 try {
  await page.goto(origin+'/poe2-candidate/poe2',{waitUntil:'domcontentloaded'})
  await page.getByLabel('构筑分享码',{exact:true}).fill(fs.readFileSync(root+'/evidence/link-research/user-ninja-code-20260920.txt','utf8').trim())
  await page.getByRole('button',{name:'导入构筑',exact:true}).click()
  const card=page.getByRole('region',{name:'已解析角色',exact:true})
  await card.waitFor({timeout:90000})
  const summary=await card.innerText();assert.ok(summary.includes('佣兵'));assert.ok(summary.includes('古灵使徒斗士'));assert.ok(!summary.includes('Mercenary'))
  await page.screenshot({path:out+'/summary.png',fullPage:true,mask:[page.locator('textarea')]})
  await page.getByRole('button',{name:'继续调整与对比',exact:true}).click()
  assert.ok((await page.getByLabel('装备槽位').innerText()).includes('头盔'))
  await page.getByRole('button',{name:'计算基线',exact:true}).click()
  await page.getByText('原始构筑：已完成',{exact:true}).waitFor({timeout:90000})
  await page.getByRole('button',{name:'查看完整详情 →',exact:true}).click()
  await page.getByRole('heading',{name:'第三步 · 查看详情',exact:true}).waitFor()
  const detail=await page.locator('body').innerText()
  for(const name of ['盾墙','大地震击'])assert.ok(detail.includes(name),name)
  for(const name of ['Shield Wall','Sunder','Gemling Legionnaire'])assert.ok(!detail.includes(name),'default English '+name)
  await page.setViewportSize({width:390,height:844})
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+4))
  await page.screenshot({path:out+'/details-mobile.png',fullPage:true,mask:[page.locator('textarea')]})
  assert.deepEqual(errors,[])
  fs.writeFileSync(out+'/browser.json',JSON.stringify({passed:true,summaryChinese:true,skillsChinese:true,slotsChinese:true,mobile390:true,errors},null,2))
  console.log('Chinese summary, slots, skill details and 390px passed')
 }catch(e){console.error('Chinese UI check failed: '+String(e.message).replace(/https?:\/\/\S+/g,'[URL]'));process.exitCode=1}
 finally{await browser.close()}
}
main().catch(()=>{console.error('Chinese UI launch failed');process.exitCode=1})
