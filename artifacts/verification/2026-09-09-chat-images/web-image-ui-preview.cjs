const {chromium} = require('/Users/boyuan/Documents/wow_mini_program/node_modules/playwright-core')
const fs = require('fs/promises'); const path = require('path')
const root = '/Users/boyuan/.codex/worktrees/a330/wow_mini_program/apps/mini-taro/dist/h5'
;(async () => {
 const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
 const context = await browser.newContext({viewport:{width:1440,height:1050}})
 await context.addCookies([{name:'__Host-chickenbro-csrf',value:'preview-only-csrf-token-12345',url:'https://chat-image-preview.test',secure:true}])
 const page = await context.newPage()
 const now = '2026-09-09T05:00:00Z'
 const conversation = {id:'conversation-one',title:'截图提问 · 本地界面演示',status:'active',createdAt:now,updatedAt:now}
 const image = {id:'image-one',mimeType:'image/png',width:640,height:400}
 let png
 await page.route('**/*', async route => {
  const url = new URL(route.request().url())
  if (url.hostname !== 'chat-image-preview.test') return route.abort()
  const send = body => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
  if(url.pathname==='/api/v2/me') return send({connected:true,displayName:'本地演示'})
  if(url.pathname==='/api/v2/me/avatar') return send({avatarDataUrl:null})
  if(url.pathname.endsWith('/image-capabilities')) return send({enabled:true,maxImages:3,maxBytes:5242880})
  if(url.pathname.endsWith('/chat/images') && route.request().method()==='POST') return send(image)
  if(url.pathname.endsWith('/chat/images/image-one')) return send({dataUrl:'data:image/png;base64,'+png})
  if(url.pathname.endsWith('/chat/conversations')) return send({items:[conversation],nextCursor:null})
  if(url.pathname.endsWith('/chat/conversations/conversation-one')) return send({...conversation,messages:[{id:'message-one',role:'user',content:'帮我看看这张截图里的技能覆盖情况',createdAt:now,images:[image]},{id:'message-two',role:'assistant',content:'可以，请结合战斗时间与关键技能使用次数一起核对。',createdAt:now}]})
  if(url.pathname.startsWith('/api/')) return send({})
  let file = url.pathname === '/' || !path.extname(url.pathname) ? 'index.html' : url.pathname.slice(1)
  try {const data = await fs.readFile(path.join(root,file)); return route.fulfill({body:data,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.html')?'text/html':'application/octet-stream'})}catch{return route.fulfill({status:404,body:''})}
 })
 await page.goto('https://chat-image-preview.test/')
 await page.getByRole('button',{name:'添加图片'}).waitFor()
 png = await page.evaluate(() => {const c=document.createElement('canvas'); c.width=640;c.height=400;const x=c.getContext('2d');x.fillStyle='#172a35';x.fillRect(0,0,640,400);x.fillStyle='#f7db8c';x.font='32px sans-serif';x.fillText('技能覆盖 · 本地演示图',36,60);['火焰震击 92%','熔岩爆裂 38 次','闪电箭 61 次'].forEach((t,i)=>{x.fillStyle='#e3e9eb';x.font='24px sans-serif';x.fillText(t,36,130+i*76);x.fillStyle='#b35e3c';x.fillRect(270,107+i*76,260-i*55,28)});return c.toDataURL('image/png').split(',')[1]})
 const chooser = page.waitForEvent('filechooser')
 await page.getByRole('button',{name:'添加图片'}).click()
 await (await chooser).setFiles({name:'local-ui-demo.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')})
 await page.getByText('已就绪',{exact:true}).waitFor()
 await page.getByText('查看图片',{exact:true}).click()
 await page.getByLabel('消息内容').fill('这是我的战斗截图，帮我看看哪里可以提升？')

 await page.waitForFunction(() => document.querySelectorAll('[aria-label="预览图片"]').length === 2 && [...document.querySelectorAll('taro-image-core img')].filter(i => i.src.startsWith('data:image')).every(i => i.complete))
 await page.screenshot({path:'/tmp/chat-image-ui-preview.png',fullPage:true})
 await page.getByLabel('预览图片').first().click()
 await page.getByText('关闭预览',{exact:true}).waitFor()
 await page.screenshot({path:'/tmp/chat-image-ui-expanded.png',fullPage:true})
 console.log('UI-only screenshot /tmp/chat-image-ui-preview.png; mocked requests, no production network')
 await browser.close()
})().catch(e=>{console.error(e);process.exit(1)})
