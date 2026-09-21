// @vitest-environment jsdom
import {act, createElement} from 'react'
import {createRoot, type Root} from 'react-dom/client'
import {beforeEach, afterEach, expect, it, vi} from 'vitest'
const api = vi.hoisted(() => ({deleteBuild: vi.fn(), getTree: vi.fn(), listBuilds: vi.fn(), listJobs: vi.fn(), importBuild: vi.fn(), calculate: vi.fn(), getJob: vi.fn(), getImport: vi.fn(), compare: vi.fn(), exportBuild: vi.fn(), craftingLink: vi.fn()}))
vi.mock('@wow-mini/api-client', () => ({wowApi: {poe2: api}}))
import WebPoe2 from './WebPoe2'
const build = {id: 'build-a', title: '测试 BD', gameVersion: '0.5', league: '', summary: {level: 96, className: 'Mercenary', ascendancy: 'Gemling Legionnaire'}, inputSha256: 'a'.repeat(64), engineVersion: 'v0.23.1', createdAt: '2026-09-18T00:00:00Z'}
const code = 'eNrtWEtv2zgQ_iseL1-testString1234=='
const success = (payload: unknown) => ({payload, fromFallback: false, error: ''})
const baselineResult = {stats: {Life: 1234, Str: 231}, unsupported: [], skills: [{index: 1, gems: [{name: 'Shield Wall', level: 20}]}], skillSetup: [{index: 1, source: 'configured', slot: '', gems: [{name: 'Shield Wall', level: 20, kind: 'skill'}, {name: 'Bleed III', level: 1, kind: 'support'}]}], allocatedNodes: [1], effectiveConfig: {enemyIsBoss: 'Pinnacle'}, engineVersion: 'test', exportCode: 'test-code'}
const savedBaseline = {id: 'baseline', buildId: build.id, status: 'succeeded', changes: {}, result: baselineResult}
let container: HTMLDivElement, root: Root
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  vi.resetAllMocks()
  sessionStorage.clear()
  api.listBuilds.mockResolvedValue(success({items: []}))
  api.getTree.mockResolvedValue({fromFallback: true, problemCode: 'POE2_TREE_UNAVAILABLE'})
  api.listJobs.mockResolvedValue(success({items: [savedBaseline]}))
  api.importBuild.mockResolvedValue(success(build))
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => {await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals()})
const button = (text: string) => Array.from(container.querySelectorAll('button')).find(b => b.textContent === text)!
const render = (csrfToken = 'csrf') => act(async () => root.render(createElement(WebPoe2, {auth: {kind: 'web', csrfToken}})))
const enter = (text: string) => act(async () => {
  const el = container.querySelector<HTMLTextAreaElement>('[aria-label="构筑分享码"]')!
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(el, text)
  el.dispatchEvent(new Event('input', {bubbles: true}))
})
const click = (text: string) => act(async () => button(text).click())
it('imports once and immediately shows character, attributes and skills in a two-step flow', async () => {
  sessionStorage.setItem('poe2-import:01', 'old-import')
  await render()
  expect(container.textContent).toContain('IMPORT CODE FOR PATH OF BUILDING')
  expect(container.querySelector('a[href="https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases"]')).not.toBeNull()
  expect(container.querySelector('input[type="file"]')).toBeNull()
  expect(container.querySelector('[aria-label="角色链接"]')).toBeNull()
  expect(container.textContent).not.toContain('使用示例构筑')
  expect(api.getImport).not.toHaveBeenCalled()
  await enter(`  ${code}\n`); await click('导入构筑')
  expect(api.importBuild).toHaveBeenCalledWith({source: code, title: '我的 POE2 构筑', league: ''}, expect.anything())
  const card = container.querySelector('[aria-label="已解析角色"]')!
  expect(card.textContent).toContain('96 级'); expect(card.textContent).toContain('佣兵'); expect(card.textContent).toContain('古灵使徒斗士')
  expect(card.textContent).not.toContain('已保存为构筑'); expect(card.textContent).not.toContain('信息来自本次'); expect(card.textContent).not.toContain('继续对比')
  expect(button('① 导入').getAttribute('aria-current')).toBe('step')
  expect(container.querySelectorAll('nav[aria-label="构筑操作步骤"] button')).toHaveLength(2)
  expect(container.querySelector('[aria-label="构筑详情"]')?.textContent).toContain('1,234')
  expect(container.querySelector('[aria-label="构筑详情"]')?.textContent).toContain('盾墙')
  expect(container.querySelector('[aria-label="技能搭配"] article h4')?.textContent).toContain('盾墙')
  expect(container.querySelector('[aria-label="技能搭配"] article ul')?.textContent).toContain('流血 III')
  expect(container.querySelector('[aria-label="构筑详情"]')?.textContent).not.toContain('巅峰首领')
  expect(api.getTree).toHaveBeenCalledWith(build.id, expect.anything(), undefined)
  expect(api.calculate).not.toHaveBeenCalled()
  await click('② 对比')
  expect(button('② 对比').getAttribute('aria-current')).toBe('step')
})
it.each(['', '  ', 'https://poe.ninja/poe2/builds/char', '<PathOfBuilding2/>', '明显不是导入码', 'invalid code!'])('rejects a non-code input before calling the API: %s', async input => {
  await render(); await enter(input); await click('导入构筑')
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('这里只接受 PoB 2 字符串')
  expect(api.importBuild).not.toHaveBeenCalled()
})
it('shows server rejection for a syntactically plausible but invalid code', async () => {
  api.importBuild.mockResolvedValue({fromFallback: true, problemCode: 'POE2_BUILD_FORMAT_INVALID'})
  await render(); await enter(code); await click('导入构筑')
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('这里只接受 PoB 2 字符串')
  expect(container.querySelector('[aria-label="已解析角色"]')).toBeNull()
})
it('clears the success card for a new import while keeping saved history accessible', async () => {
  await render(); await enter(code); await click('导入构筑'); await click('＋ 导入新构筑')
  expect(container.querySelector('[aria-label="已解析角色"]')).toBeNull()
  expect(container.querySelector<HTMLTextAreaElement>('[aria-label="构筑分享码"]')?.value).toBe('')
  expect(button('② 对比').disabled).toBe(true)
  const history = container.querySelector<HTMLButtonElement>('aside button[aria-pressed]')!
  expect(history.textContent).toContain(build.title)
  await act(async () => history.click())
  expect(button('① 导入').getAttribute('aria-current')).toBe('step')
})
it('merges late history without replacing the newly parsed build or moving the current step', async () => {
  let finish!: (value: unknown) => void
  api.listBuilds.mockImplementationOnce(() => new Promise(resolve => {finish = resolve}))
  await render(); await enter(code); await click('导入构筑')
  await act(async () => finish(success({items: [{...build, id: 'old', title: '旧构筑'}]})))
  expect(container.querySelector('aside button[aria-pressed="true"]')?.textContent).toContain(build.title)
  expect(container.querySelector('[aria-label="已解析角色"]')?.textContent).toContain('96 级')
  expect(container.textContent).toContain('旧构筑')
  expect(button('① 导入').getAttribute('aria-current')).toBe('step')
  expect(api.listJobs).not.toHaveBeenCalledWith('old', expect.anything())
})
it('ignores an old account import response after account change', async () => {
  let finish!: (value: unknown) => void
  api.importBuild.mockImplementationOnce(() => new Promise(resolve => {finish = resolve}))
  await render('A'); await enter(code); await click('导入构筑')
  await render('B'); await act(async () => finish(success(build)))
  expect(container.querySelector('[aria-label="已解析角色"]')).toBeNull()
  expect(container.textContent).not.toContain(build.title)
  expect(container.querySelector<HTMLTextAreaElement>('[aria-label="构筑分享码"]')?.value).toBe('')
})
it('keeps comparison focused and retains character and tree on the import step', async () => {
  api.listBuilds.mockResolvedValue(success({items: [build]}))
  const result = {stats: {Life: 100, CombinedDPS: 10}, unsupported: [], skills: [], allocatedNodes: [], effectiveConfig: {}, engineVersion: 'test', exportCode: 'test-code'}
  api.listJobs.mockResolvedValue(success({items: [
    {id: 'candidate', buildId: build.id, status: 'succeeded', changes: {level: 91}, result},
    {id: 'baseline', buildId: build.id, status: 'succeeded', changes: {}, result},
  ]}))
  api.compare.mockResolvedValue(success({baselineChanges: {}, candidateChanges: {level: 91}, metrics: {Life: {baseline: 100, candidate: 110, delta: 10, percent: 10}}}))
  await render()
  expect(api.compare).toHaveBeenCalledWith(['baseline', 'candidate'], expect.anything())
  await click('② 对比')
  expect(container.textContent).toContain('方案对比')
  expect(container.querySelector('[aria-label="查看方案"]')).toBeNull()
  expect(container.querySelector('[aria-label="构筑详情"]')).toBeNull()
  expect(container.querySelector('[aria-label="构筑天赋树"]')).toBeNull()
  expect(container.textContent).not.toContain('计算记录与状态')
  expect(button('计算方案')).toBeDefined()
  await click('① 导入')
  expect(container.querySelector('[aria-label="构筑详情"]')).not.toBeNull()
  expect(container.querySelector('[aria-label="构筑天赋树"]')).not.toBeNull()
  expect(container.textContent).toContain('技能搭配')
})
it('automatically reads legacy build details and offers retry after a failed calculation', async () => {
  api.listBuilds.mockResolvedValue(success({items: [build]}))
  api.listJobs.mockResolvedValue(success({items: []}))
  api.calculate.mockResolvedValue(success({id: 'job-a', buildId: build.id, status: 'failed', changes: {}, errorCode: 'POE2_ENGINE_UNAVAILABLE', result: null}))
  await render()
  expect(api.calculate).toHaveBeenCalledWith({buildId: build.id, changes: {}, idempotencyKey: `overview:${build.id}`}, expect.anything())
  await click('② 对比'); await click('重新读取原始构筑')
  expect(container.textContent).toContain('POE2_ENGINE_UNAVAILABLE')
  expect(container.textContent).not.toContain('计算成功')
})
it('maps verified Chinese gems to original engine names and blocks an unverified Chinese input', async () => {
  api.listBuilds.mockResolvedValue(success({items: [build]}))
  api.listJobs.mockResolvedValue(success({items: [{id: 'baseline', buildId: build.id, status: 'succeeded', changes: {}, result: {stats: {}, unsupported: [], skills: [], allocatedNodes: [], effectiveConfig: {}}}]}))
  api.calculate.mockResolvedValue(success({id: 'candidate', buildId: build.id, status: 'failed', changes: {}, result: null}))
  await render(); await click('② 对比')
  const select = container.querySelector<HTMLSelectElement>('select')!
  await act(async () => {select.value = 'gems'; select.dispatchEvent(new Event('change', {bubbles: true}))})
  const textarea = container.querySelector<HTMLTextAreaElement>('textarea')!
  const input = async (text: string) => act(async () => {Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, text); textarea.dispatchEvent(new Event('input', {bubbles: true}))})
  await input('未知技能 III | 20 | 0'); await click('计算方案')
  expect(api.calculate).not.toHaveBeenCalled()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('国服名称待核实')
  await input('盾墙 | 20 | 0'); await click('计算方案')
  expect(api.calculate).toHaveBeenCalledWith(expect.objectContaining({changes: {skillGroups: [{index: 1, gems: [{name: 'Shield Wall', level: 20, quality: 0}]}]}}), expect.anything())
})
it('shows a recoverable error when build history cannot be read', async () => {
  api.listBuilds.mockResolvedValue({payload: {items: []}, fromFallback: true, problemCode: 'AUTH_REQUIRED'})
  await render()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('AUTH_REQUIRED')
})

it('deletes only after confirmation and switches to the remaining build', async () => {
  api.listBuilds.mockResolvedValue(success({items: [build, {...build, id: 'build-b', title: '另一构筑'}]}))
  api.deleteBuild.mockResolvedValue(success({deleted: true}))
  await act(async () => root.render(createElement(WebPoe2, {auth: {kind: 'web', csrfToken: 'csrf'}})))
  const remove = () => container.querySelector<HTMLButtonElement>('[aria-label="删除构筑：测试 BD"]')!
  await act(async () => remove().click())
  expect(api.deleteBuild).not.toHaveBeenCalled()
  await act(async () => button('取消').click())
  expect(remove()).toBeTruthy()
  await act(async () => remove().click())
  await act(async () => button('确认删除').click())
  expect(api.deleteBuild).toHaveBeenCalledWith(build.id, {kind: 'web', csrfToken: 'csrf'})
  expect(remove()).toBeNull()
  expect(container.querySelector('[aria-pressed="true"]')?.textContent).toContain('另一构筑')
})

it('keeps the build on deletion failure and shows the error', async () => {
  api.listBuilds.mockResolvedValue(success({items: [build]}))
  api.deleteBuild.mockResolvedValue({fromFallback: true, problemCode: '删除失败'})
  await act(async () => root.render(createElement(WebPoe2, {auth: {kind: 'web', csrfToken: 'csrf'}})))
  await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="删除构筑：测试 BD"]')!.click())
  await act(async () => button('确认删除').click())
  expect(container.querySelector('[aria-label="删除构筑：测试 BD"]')).toBeTruthy()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('删除失败')
})

it('copies the exact build ID and reports clipboard failure', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', {clipboard: {writeText}})
  api.listBuilds.mockResolvedValue(success({items: [build]}))
  await render()
  expect(container.querySelector('[aria-label="已解析角色"] code')?.textContent).toBe(build.id)
  await click('复制 ID')
  expect(writeText).toHaveBeenCalledWith(build.id)
  expect(container.textContent).toContain('已复制，可粘贴到鸡哥对话中')
  writeText.mockRejectedValueOnce(new Error('denied'))
  await click('复制 ID')
  expect(container.textContent).toContain('复制失败，请选中构筑 ID 手动复制')
})
