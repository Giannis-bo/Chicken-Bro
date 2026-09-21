// @vitest-environment jsdom
import {act, createElement} from 'react'
import {createRoot, type Root} from 'react-dom/client'
import {beforeEach, afterEach, expect, it, vi} from 'vitest'
const api = vi.hoisted(() => ({createImport: vi.fn(), getImport: vi.fn(), supplyImportSource: vi.fn(), retryImport: vi.fn(), cancelImport: vi.fn()}))
vi.mock('@wow-mini/api-client', () => ({wowApi: {poe2: api}}))
import Poe2CharacterImport, {validCharacterUrl} from './Poe2CharacterImport'
const ok = (payload: unknown) => ({payload, fromFallback: false})
const packet = {id: 'import-a', provider: 'ninja', status: 'needs_input', preview: {character: '角色甲', sourceRelation: 'user_supplied'}, issues: [], nextAction: 'supply_pob', buildId: null, baselineJobId: null}
const ninja = 'https://poe.ninja/poe2/profile/account/league/character/name'
let container: HTMLDivElement, root: Root
const onReady = vi.fn()
const auth = {kind: 'web' as const, csrfToken: 'session-a'}
const button = (text: string) => Array.from(container.querySelectorAll('button')).find(b => b.textContent === text)!
const input = async (selector: string, text: string) => {await act(async () => {const el = container.querySelector(selector)!; Object.getOwnPropertyDescriptor(el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value')!.set!.call(el, text); el.dispatchEvent(new Event('input', {bubbles: true}))})}
const render = async (token = 'session-a') => act(async () => root.render(createElement(Poe2CharacterImport, {auth: {...auth, csrfToken: token}, onReady})))
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); vi.resetAllMocks(); sessionStorage.clear()
  vi.stubGlobal('crypto', {randomUUID: () => 'request-key', subtle: {digest: vi.fn(async (_: string, data: Uint8Array) => new Uint8Array([data[data.length - 1]!]).buffer)}})
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => {await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals()})
it('validates separate sources and rejects malformed identifiers', () => {
  expect(validCharacterUrl(ninja, 'ninja')).toBe(true); expect(validCharacterUrl(ninja, 'wegame')).toBe(false)
  expect(validCharacterUrl('https://www.wegame.com.cn/helper/poe2/#/share/example', 'wegame')).toBe(true)
  for (const suffix of ['%2F', '%25', '%ZZ']) expect(validCharacterUrl(ninja + suffix, 'ninja')).toBe(false)
  expect(validCharacterUrl('https://poe.ninja.evil/poe2/profile/a/b/character/c', 'ninja')).toBe(false)
})
it('guides ninja copy PoB and requires user confirmation before supplying', async () => {
  api.createImport.mockResolvedValue(ok(packet)); api.supplyImportSource.mockResolvedValue(ok({...packet, status: 'queued', nextAction: null}))
  await render(); await act(async () => button('国际服 · poe.ninja').click()); await input('[aria-label="角色链接"]', ninja)
  await act(async () => button('读取角色').click())
  expect(api.createImport).toHaveBeenCalledWith(expect.objectContaining({provider: 'ninja', url: ninja}), auth)
  expect(container.textContent).toContain('Copy PoB'); expect(container.textContent).toContain('尚未验证')
  await input('[aria-label="补充 PoB"]', '<PathOfBuilding2/>')
  expect(button('补充并计算基线').disabled).toBe(true)
  await act(async () => container.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click())
  await act(async () => button('补充并计算基线').click())
  expect(api.supplyImportSource).toHaveBeenCalled(); expect(onReady).not.toHaveBeenCalled()
})
it('groups WeGame gaps and retains jewels plus version and item limitations', async () => {
  api.createImport.mockResolvedValue(ok({...packet, provider: 'wegame', issues: [{code: 'JEWELS_MISSING', path: 'jewels', message: '缺少珠宝'}, {code: 'MOD_UNMAPPED', path: 'items[0]', message: '未支持词缀'}, {code: 'VERSION_UNKNOWN', path: 'version', message: '版本未知'}]}))
  await render(); await input('[aria-label="角色链接"]', 'https://www.wegame.com.cn/helper/poe2/#/share/example'); await act(async () => button('读取角色').click())
  expect(container.querySelectorAll('details')).toHaveLength(3); expect(container.textContent).toContain('珠宝资料缺失'); expect(container.textContent).toContain('版本或任务信息待确认'); expect(onReady).not.toHaveBeenCalled()
})
it('recovers same session with only an import id and delivers existing ready ids', async () => {
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockResolvedValue(ok({...packet, status: 'ready', buildId: 'build-a', baselineJobId: 'job-a'}))
  await render(); expect(api.getImport).toHaveBeenCalledWith('import-a', auth); expect(onReady).toHaveBeenCalledWith('build-a', 'job-a')
  expect(sessionStorage.getItem('poe2-import:61')).toBeNull(); expect(sessionStorage.length).toBe(0)
})
it('cancels visibly and isolates late source and account results', async () => {
  let resolve!: (v: unknown) => void
  api.createImport.mockImplementationOnce(() => new Promise(r => {resolve = r}))
  await render(); await input('[aria-label="角色链接"]', 'https://www.wegame.com.cn/helper/poe2/#/share/example'); await act(async () => button('读取角色').click())
  await act(async () => button('国际服 · poe.ninja').click()); await act(async () => resolve(ok({...packet, provider: 'wegame'})))
  expect(container.textContent).not.toContain('角色甲')
  api.createImport.mockResolvedValue(ok(packet)); api.cancelImport.mockResolvedValue(ok({...packet, status: 'cancelled', nextAction: null}))
  await input('[aria-label="角色链接"]', ninja); await act(async () => button('读取角色').click()); await act(async () => button('取消导入').click())
  expect(container.textContent).toContain('已取消导入')
  api.getImport.mockImplementationOnce(() => new Promise(r => {resolve = r}))
  await render('session-c'); await render('session-b')
  expect(container.textContent).not.toContain('角色甲'); expect((container.querySelector('[aria-label="角色链接"]') as HTMLInputElement).value).toBe('')
})
it('ignores a restored account A response after switching to account B', async () => {
  let resolve!: (v: unknown) => void
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockImplementationOnce(() => new Promise(r => {resolve = r}))
  await render(); expect(api.getImport).toHaveBeenCalled()
  await render('session-b')
  await act(async () => resolve(ok({...packet, status: 'ready', buildId: 'private-build', baselineJobId: 'private-job'})))
  expect(onReady).not.toHaveBeenCalled(); expect(container.textContent).not.toContain('角色甲'); expect(sessionStorage.getItem('poe2-import:62')).toBeNull()
})
it('polls pending stages and offers explicit retry after a failure', async () => {
  vi.useFakeTimers()
  try {
    api.createImport.mockResolvedValue(ok({...packet, status: 'queued', nextAction: null}))
    api.getImport.mockResolvedValue(ok({...packet, status: 'failed', nextAction: null}))
    api.retryImport.mockResolvedValue(ok({...packet, status: 'queued', nextAction: null}))
    await render(); await act(async () => button('国际服 · poe.ninja').click()); await input('[aria-label="角色链接"]', ninja); await act(async () => button('读取角色').click())
    await act(async () => vi.advanceTimersByTimeAsync(2000))
    expect(container.textContent).toContain('导入失败'); await act(async () => button('重试导入').click())
    expect(api.retryImport).toHaveBeenCalledWith('import-a', {idempotencyKey: 'request-key'}, auth); expect(container.textContent).toContain('等待读取')
  } finally {vi.useRealTimers()}
})
it('ignores a deferred poll after cancellation and a new same-source import', async () => {
  vi.useFakeTimers()
  try {
    let finish!: (v: unknown) => void
    api.createImport.mockResolvedValueOnce(ok({...packet, status: 'queued', nextAction: null})).mockResolvedValueOnce(ok({...packet, id: 'import-new'}))
    api.getImport.mockImplementationOnce(() => new Promise(resolve => {finish = resolve}))
    api.cancelImport.mockResolvedValue(ok({...packet, status: 'cancelled', nextAction: null}))
    await render(); await act(async () => button('国际服 · poe.ninja').click()); await input('[aria-label="角色链接"]', ninja); await act(async () => button('读取角色').click())
    await act(async () => vi.advanceTimersByTimeAsync(2000))
    await act(async () => button('取消导入').click()); expect(container.textContent).toContain('已取消导入')
    await act(async () => button('读取角色').click())
    await act(async () => finish(ok({...packet, status: 'ready', buildId: 'old-build', baselineJobId: 'old-job'})))
    expect(onReady).not.toHaveBeenCalled(); expect(sessionStorage.getItem('poe2-import:61')).toBe('import-new'); expect(container.textContent).toContain('需要补充完整 PoB')
  } finally {vi.useRealTimers()}
})
it('does not let an old restore ready result replace an explicit new import', async () => {
  let finish!: (v: unknown) => void
  sessionStorage.setItem('poe2-import:61', 'import-old')
  api.getImport.mockImplementationOnce(() => new Promise(resolve => {finish = resolve}))
  api.createImport.mockResolvedValue(ok({...packet, provider: 'wegame', id: 'import-new'}))
  await render(); await input('[aria-label="角色链接"]', 'https://www.wegame.com.cn/helper/poe2/#/share/example'); await act(async () => button('读取角色').click())
  await act(async () => finish(ok({...packet, id: 'import-old', status: 'ready', buildId: 'old-build', baselineJobId: 'old-job'})))
  expect(onReady).not.toHaveBeenCalled(); expect(sessionStorage.getItem('poe2-import:61')).toBe('import-new'); expect(button('国服 · WeGame').getAttribute('aria-pressed')).toBe('true')
})
it.each(['fallback', 'rejection'])('offers recovery when a late abandoned create cancellation returns %s', async failure => {
  let finish!: (v: unknown) => void
  api.createImport.mockImplementationOnce(() => new Promise(resolve => {finish = resolve}))
  if (failure === 'fallback') api.cancelImport.mockResolvedValue({fromFallback: true, payload: null, problemCode: 'NETWORK_ERROR'})
  else api.cancelImport.mockRejectedValue(new Error('offline'))
  await render(); await input('[aria-label="角色链接"]', 'https://www.wegame.com.cn/helper/poe2/#/share/example'); await act(async () => button('读取角色').click())
  await act(async () => button('国际服 · poe.ninja').click())
  await act(async () => finish(ok({...packet, provider: 'wegame', status: 'queued', nextAction: null})))
  expect(api.cancelImport).toHaveBeenCalledWith('import-a', auth); expect(container.textContent).toContain('上一个来源任务未能取消'); expect(sessionStorage.getItem('poe2-import:61')).toBe('import-a')
  api.getImport.mockResolvedValue(ok({...packet, provider: 'wegame', status: 'queued', nextAction: null}))
  await act(async () => button('恢复未取消任务').click())
  expect(api.getImport).toHaveBeenCalledWith('import-a', auth); expect(button('取消导入')).toBeDefined(); expect(button('国服 · WeGame').getAttribute('aria-pressed')).toBe('true')
})
it('does not cancel an old account late create or show its cancellation feedback after auth changes', async () => {
  let finish!: (v: unknown) => void
  api.createImport.mockImplementationOnce(() => new Promise(resolve => {finish = resolve}))
  await render(); await input('[aria-label="角色链接"]', 'https://www.wegame.com.cn/helper/poe2/#/share/example'); await act(async () => button('读取角色').click())
  await act(async () => button('国际服 · poe.ninja').click()); await render('session-b')
  await act(async () => finish(ok({...packet, status: 'queued', nextAction: null})))
  expect(api.cancelImport).not.toHaveBeenCalled(); expect(container.textContent).not.toContain('上一个来源任务'); expect(sessionStorage.getItem('poe2-import:62')).toBeNull()
})
it('finishes the session fingerprint after an action and persists only the current import id', async () => {
  let finishHash!: (v: ArrayBuffer) => void
  vi.stubGlobal('crypto', {randomUUID: () => 'key', subtle: {digest: () => new Promise<ArrayBuffer>(resolve => {finishHash = resolve})}})
  api.createImport.mockResolvedValue(ok({...packet, provider: 'wegame', id: 'import-new'}))
  await render(); await input('[aria-label="角色链接"]', 'https://www.wegame.com.cn/helper/poe2/#/share/example'); await act(async () => button('读取角色').click())
  await act(async () => finishHash(new Uint8Array([97]).buffer))
  expect(sessionStorage.getItem('poe2-import:61')).toBe('import-new'); expect(sessionStorage.length).toBe(1); expect(api.getImport).not.toHaveBeenCalled()
})
it('keeps ready recovery after loading fails and consumes it only after a successful retry', async () => {
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockResolvedValue(ok({...packet, status: 'ready', buildId: 'build-a', baselineJobId: 'job-a'}))
  onReady.mockRejectedValueOnce(new Error('baseline unavailable')).mockResolvedValue(undefined)
  await render(); expect(container.textContent).toContain('baseline unavailable'); expect(sessionStorage.getItem('poe2-import:61')).toBe('import-a')
  await act(async () => root.render(null)); await render()
  expect(onReady).toHaveBeenCalledTimes(2); expect(sessionStorage.getItem('poe2-import:61')).toBeNull()
})
it('opens the restored ninja task source even after the editable link changes', async () => {
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockResolvedValue(ok({...packet, preview: {sourceUrl: ninja}}))
  await render()
  await input('[aria-label="角色链接"]', 'https://poe.ninja/poe2/profile/other/league/character/other')
  const link = container.querySelector<HTMLAnchorElement>('a')!
  expect(link?.textContent).toBe('打开 poe.ninja 角色页'); expect(link?.href).toBe(ninja)
  expect(link?.target).toBe('_blank'); expect(link?.rel).toBe('noopener noreferrer')
})
it.each(['javascript:alert(1)', 'https://poe.ninja.evil/poe2/profile/a/b/character/c', 'https://user:pass@poe.ninja/poe2/profile/a/b/character/c', 'https://poe.ninja/poe2/profile/a/b/character/%2F'])('does not render an unsafe task source link: %s', async sourceUrl => {
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockResolvedValue(ok({...packet, preview: {sourceUrl}}))
  await render(); expect(container.querySelector('a')).toBeNull()
})
it('consumes a successful delivery after unmount while preserving a newer recovery record', async () => {
  let finish!: (accepted: boolean) => void
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockResolvedValue(ok({...packet, status: 'ready', buildId: 'build-a', baselineJobId: 'job-a'}))
  onReady.mockImplementationOnce(() => new Promise<boolean>(resolve => {finish = resolve}))
  await render(); await act(async () => root.render(null)); await act(async () => finish(true))
  expect(sessionStorage.getItem('poe2-import:61')).toBeNull()
  sessionStorage.setItem('poe2-import:61', 'import-a')
  onReady.mockImplementationOnce(() => new Promise<boolean>(resolve => {finish = resolve}))
  await render(); await act(async () => root.render(null)); sessionStorage.setItem('poe2-import:61', 'newer-import')
  await act(async () => finish(true)); expect(sessionStorage.getItem('poe2-import:61')).toBe('newer-import')
})
it('retains recovery when the parent rejects delivery after an account transition', async () => {
  sessionStorage.setItem('poe2-import:61', 'import-a')
  api.getImport.mockResolvedValue(ok({...packet, status: 'ready', buildId: 'build-a', baselineJobId: 'job-a'}))
  onReady.mockResolvedValue(false)
  await render(); expect(sessionStorage.getItem('poe2-import:61')).toBe('import-a')
})
