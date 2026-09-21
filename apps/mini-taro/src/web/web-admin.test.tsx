// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.mock('@wow-mini/api-client',()=>({wowApi:{admin:{}}}))
import WebAdmin, { beijingDate, presetDates, formatRate } from './WebAdmin'
import { isAdminOverview } from '@wow-mini/domain'
import { readWebView, webViewHref } from './web-routing'
const ok=(payload:unknown)=>({payload,fromFallback:false,error:''})
const zero={total:0,succeeded:0,failed:0,running:0,successRate:null,avgSeconds:null,p95Seconds:null}
const fixture={game:'wow',builds:0,start:'2026-09-03',end:'2026-09-09',timezone:'Asia/Shanghai',generatedAt:'2026-09-09T04:00:00Z',scope:'current_qq_users',users:{total:0,new:0,active:0},chat:{...zero,resolved:0,unresolved:0,feedbackRate:null,resolutionRate:null},simc:{...zero,queued:0,cancelled:0,invalidResults:0},daily:[{date:'2026-09-09',newUsers:0,activeUsers:0,questions:0,simulations:0,builds:0}],specializations:[]}
let node:HTMLDivElement, root:Root
const client={access:vi.fn(),overview:vi.fn()}
beforeEach(()=>{vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);node=document.createElement('div');document.body.append(node);root=createRoot(node);vi.clearAllMocks()})
afterEach(async()=>{await act(async()=>root.unmount());node.remove();vi.unstubAllGlobals()})
async function render(){await act(async()=>root.render(createElement(WebAdmin,{auth:{kind:'web',csrfToken:'csrf'},accountLabel:'本人',onLogout:vi.fn(),client})))}
it('denies other QQ accounts before asking for aggregate data',async()=>{
  client.access.mockResolvedValue(ok({isAdmin:false,accountId:'11111111-1111-4111-8111-111111111111'}))
  await render();expect(node.textContent).toContain('此账号没有后台访问权限');expect(client.overview).not.toHaveBeenCalled()
})
it('shows empty metrics as no sample, distinguishes errors from zero and clears prior data',async()=>{
  client.access.mockResolvedValue(ok({isAdmin:true,accountId:'11111111-1111-4111-8111-111111111111'}))
  client.overview.mockResolvedValue(ok(fixture));await render()
  expect(node.textContent).toContain('所选期间暂无模拟任务');expect(node.textContent).toContain('累计用户');expect(node.textContent).not.toContain('0.0%')
  client.overview.mockResolvedValue({payload:fixture,fromFallback:true,error:'offline'})
  await act(async()=>Array.from(node.querySelectorAll('button')).find(b=>b.textContent==='刷新')!.click())
  expect(node.textContent).toContain('统计数据暂不可用');expect(node.textContent).not.toContain('累计用户')
})
it('routes admin and applies Beijing date arithmetic independent of host timezone',()=>{
  expect(readWebView(new URL('https://www.chickenbro.cloud/admin'))).toBe('admin')
  expect(webViewHref('admin',new URL('https://www.chickenbro.cloud/simc'))).toBe('/admin')
  expect(beijingDate(new Date('2026-09-08T16:00:00Z'))).toBe('2026-09-09')
  expect(presetDates(7,new Date('2026-09-08T16:00:00Z'))).toEqual(['2026-09-03','2026-09-09'])
  expect(formatRate(null)).toBe('—');expect(formatRate(0)).toBe('0.0%')
})
it('validates the whole aggregate contract and rejects corrupt rates and arrays',()=>{
  expect(isAdminOverview(fixture)).toBe(true)
  expect(isAdminOverview({...fixture,chat:{...fixture.chat,successRate:NaN}})).toBe(false)
  expect(isAdminOverview({...fixture,simc:{...fixture.simc,successRate:2}})).toBe(false)
  expect(isAdminOverview({...fixture,daily:[{}]})).toBe(false)
})
it('ignores an older response after switching the date range',async()=>{
  client.access.mockResolvedValue(ok({isAdmin:true,accountId:'11111111-1111-4111-8111-111111111111'}))
  let finishOld: (value: unknown) => void = () => undefined
  client.overview.mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve})).mockResolvedValue(ok({...fixture,users:{total:7,new:3,active:2}}))
  await render()
  await act(async()=>Array.from(node.querySelectorAll('button')).find(b=>b.textContent==='近 30 天')!.click())
  await act(async()=>finishOld(ok({...fixture,users:{total:999,new:999,active:999}})))
  expect(node.textContent).not.toContain('999')
  expect(node.textContent).toContain('累计用户7')
})

it('separates POE2 metrics and ignores a late WoW response after switching games',async()=>{
  client.access.mockResolvedValue(ok({isAdmin:true,accountId:'11111111-1111-4111-8111-111111111111'}))
  let finishOld: (value: unknown) => void = () => undefined
  const {simc,...base}=fixture
  const poe={...base,game:'poe2',builds:3,poe2:{...simc,total:4}}
  expect(isAdminOverview(poe)).toBe(true)
  expect(isAdminOverview({...poe,poe2:undefined})).toBe(false)
  client.overview.mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve})).mockResolvedValue(ok(poe))
  await render()
  await act(async()=>Array.from(node.querySelectorAll('button')).find(b=>b.textContent==='POE2')!.click())
  expect(client.overview.mock.lastCall?.[3]).toBe('poe2')
  expect(node.textContent).toContain('PoB 构筑计算')
  expect(node.textContent).toContain('构筑导入3')
  expect(node.textContent).not.toContain('SimC 模拟')
  expect(node.textContent).not.toContain('职业与专精分布')
  await act(async()=>finishOld(ok({...fixture,users:{total:999,new:999,active:999}})))
  expect(node.textContent).not.toContain('999')
  expect(node.textContent).toContain('PoB 构筑计算')
})
