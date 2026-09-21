// Run on the cloud host after the isolated H5 build. All HTTP traffic is intercepted.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
const {chromium}=require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const root=process.cwd(),dist=path.join(root,'apps/mini-taro/dist/h5'),origin='https://admin-fixture.test'
const output=path.join(root,'artifacts/verification/2026-09-21-admin-games')
const zero={total:0,succeeded:0,failed:0,running:0,successRate:null,avgSeconds:null,p95Seconds:null}
function overview(game){return {game,builds:game==='poe2'?3:0,start:'2026-09-15',end:'2026-09-21',timezone:'Asia/Shanghai',generatedAt:'2026-09-21T10:00:00Z',scope:'current_qq_users',users:{total:10,new:2,active:2},chat:{...zero,total:2,succeeded:2,resolved:1,unresolved:0,feedbackRate:.5,resolutionRate:1},[game==='wow'?'simc':'poe2']:{...zero,total:4,succeeded:3,failed:1,successRate:.75,queued:0,cancelled:0,invalidResults:0},daily:[{date:'2026-09-21',newUsers:2,activeUsers:2,questions:2,simulations:4,builds:game==='poe2'?3:0}],specializations:[]}}
;(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'/opt/chickenbro-candidates/poe2-20260918/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox']})
try{
 const context=await browser.newContext();await context.addCookies([{name:'__Host-chickenbro-csrf',value:'fixture',url:origin,secure:true}])
 const page=await context.newPage(),errors=[],games=[];page.on('pageerror',e=>errors.push(e.message))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());let json
  if(url.pathname==='/api/v2/me')json={connected:true,displayName:'后台测试'}
  else if(url.pathname==='/api/v2/admin/access')json={isAdmin:true,accountId:'11111111-1111-4111-8111-111111111111'}
  else if(url.pathname==='/api/v2/admin/overview'){const game=url.searchParams.get('game');games.push(game);json=overview(game)}
  if(json)return route.fulfill({json})
  const file=path.join(dist,url.pathname==='/admin'?'index.html':url.pathname)
  if(!file.startsWith(dist+'/')||!fs.existsSync(file)||!fs.statSync(file).isFile())return route.fulfill({status:404,body:''})
  const mime={'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2'}
  await route.fulfill({body:fs.readFileSync(file),contentType:mime[path.extname(file)]||'application/octet-stream'})
 })
 const results=[]
 for(const width of [1440,390,320]){
  await page.setViewportSize({width,height:1000});await page.goto(origin+'/admin')
  await page.getByRole('heading',{name:'SimC 模拟',exact:true}).waitFor()
  await page.getByRole('button',{name:'POE2',exact:true}).click()
  await page.getByRole('heading',{name:'PoB 构筑计算',exact:true}).waitFor()
  assert.equal(await page.getByRole('heading',{name:'职业与专精分布'}).count(),0)
  await page.getByRole('button',{name:'POE2',exact:true}).click()
  assert.equal(await page.getByRole('heading',{name:'PoB 构筑计算'}).count(),1)
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)
  assert.equal(overflow,false,`overflow at ${width}`)
  await page.screenshot({path:path.join(output,`poe2-${width}.png`),fullPage:true})
  await page.getByRole('button',{name:'魔兽世界',exact:true}).click()
  await page.getByRole('heading',{name:'SimC 模拟',exact:true}).waitFor()
  assert.equal(await page.getByRole('heading',{name:'PoB 构筑计算'}).count(),0)
  results.push({width,passed:true})
 }
 assert.deepEqual(errors,[]);assert(games.includes('wow')&&games.includes('poe2'))
 fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify({mode:'cloud H5 artifact with intercepted API fixtures',results,errors},null,2))
 console.log(JSON.stringify({results,errors}))
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)})
