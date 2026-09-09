// @vitest-environment jsdom
import { act, createElement, type ComponentType, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const runtime = vi.hoisted(() => ({
  storage: new Map<string, unknown>(),
  show: new Set<() => void>(),
  load: new Set<(params: { id?: string }) => void>(),
  params: { id: 'job-from-original-route' },
  listChat: vi.fn(), listJobs: vi.fn(), getJob: vi.fn(),
  createChat: vi.fn(), getChat: vi.fn(), stream: vi.fn(), createSnapshot: vi.fn(), createJob: vi.fn(),
  keyboard: new Set<(event: { height: number }) => void>(),
  me: vi.fn(), modal: vi.fn(), avatarGet: vi.fn(), login: vi.fn(), exchangeMiniCode: vi.fn(), logout: vi.fn(), actionSheet: vi.fn(), getRuntime: vi.fn(), navigate: vi.fn(),
}))

vi.mock('@tarojs/taro', async () => {
  const { useLayoutEffect, useRef } = await import('react')
  // Taro registers callbacks; mounting after an event never replays that event.
  function useDidShow(callback: () => void) {
    const current = useRef(callback)
    current.current = callback
    useLayoutEffect(() => {
      const invoke = () => current.current()
      runtime.show.add(invoke)
      return () => { runtime.show.delete(invoke) }
    }, [])
  }
  function useLoad(callback: (params: { id?: string }) => void) {
    const current = useRef(callback)
    current.current = callback
    useLayoutEffect(() => {
      const invoke = (params: { id?: string }) => current.current(params)
      runtime.load.add(invoke)
      return () => { runtime.load.delete(invoke) }
    }, [])
  }
  return { useDidShow, useLoad, default: {
    getCurrentInstance: () => ({ router: { params: runtime.params } }),
    getWindowInfo: () => ({ windowHeight: 720 }),
    onKeyboardHeightChange: (callback: (event: { height: number }) => void) => runtime.keyboard.add(callback),
    offKeyboardHeightChange: (callback: (event: { height: number }) => void) => runtime.keyboard.delete(callback),
    showModal: runtime.modal, navigateTo: runtime.navigate, navigateBack: vi.fn(), login: async () => ({code: 'fresh-mini-code'}), showActionSheet: runtime.actionSheet,
  } }
})

vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => {
    const allowed = Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id', 'style', 'placeholder'].includes(key) || key.startsWith('data-') || key.startsWith('aria-')))
    if (props['scrollIntoView']) allowed['data-scroll-target'] = props['scrollIntoView']
    if (props['onInput']) allowed['onInput'] = (event: { currentTarget: { value: string } }) => (props['onInput'] as (event: unknown) => void)({ detail: { value: event.currentTarget.value } })
    if ('value' in props) { allowed['value'] = props['value']; allowed['onChange'] = () => undefined }
    return element(tag, allowed)
  }
  return { View: host('div'), Text: host('span'), Button: host('button'), Image: host('img'),
    ScrollView: host('div'), Textarea: host('textarea'), Input: host('input'),
    Picker: (p: Record<string, unknown>) => element('select', { 'data-field': p['data-field'], disabled: !!p['disabled'], value: p['value'], onChange: (e: {target: {value: string}}) => (p['onChange'] as (e: unknown) => void)({detail: {value: e.target.value}}) },
      (p['range'] as string[]).map((label, index) => element('option', {key: index, value: index}, label))),
    Switch: (p: Record<string, unknown>) => element('input', {type: 'checkbox', 'data-field': p['data-field'], disabled: !!p['disabled'], checked: !!p['checked'], onChange: (e: {target: {checked: boolean}}) => (p['onChange'] as (e: unknown) => void)({detail: {value: e.target.checked}}) }) }
})

vi.mock('@wow-mini/api-client', () => ({
  taroStorage: {
    get: (key: string) => runtime.storage.get(key),
    set: (key: string, value: unknown) => { runtime.storage.set(key, value) },
    remove: (key: string) => { runtime.storage.delete(key) },
  },
  wowApi: {
    avatar: { get: runtime.avatarGet },
    webAuth: { me: runtime.me, loginTestMini: runtime.login, exchangeMiniCode: runtime.exchangeMiniCode, logout: runtime.logout },
    chat: { list: runtime.listChat, create: runtime.createChat, get: runtime.getChat, streamMessage: runtime.stream },
    simc: { getRuntime: runtime.getRuntime, listJobs: runtime.listJobs, getJob: runtime.getJob, createSnapshot: runtime.createSnapshot, createJob: runtime.createJob },
  },
}))

vi.mock('./TestLoginForm', async () => {
  const { createElement: element } = await import('react')
  return { default: ({ onLogin }: { onLogin: (account: 'A' | 'B', credential: string) => Promise<void> }) =>
    element('div', { 'data-test-login': true }, ...(['A', 'B'] as const).map((account) =>
      element('button', { key: account, onClick: () => void onLogin(account, 'test-only-' + 'x'.repeat(32)) }, `Enter ${account}`))) }
})

import ChickenbroPage from '../../pages/chickenbro'
import SimcPage from '../../pages/simc'
import SimcTasksPage from '../../pages/simc/tasks'
import SimcTaskDetailPage from '../../pages/simc/task-detail'
import { wowApi } from '@wow-mini/api-client'
import { MINI_SESSION_KEY, MiniSessionStore } from './mini-session'

function success<T>(payload: T) {
  return { payload, fromFallback: false, error: '', httpStatus: 200 }
}

describe('Mini test login lifecycle', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    vi.stubGlobal('__WOW_TEST_LOGIN__', true)
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    runtime.storage.clear()
    runtime.keyboard.clear()
    runtime.show.clear()
    runtime.load.clear()
    vi.clearAllMocks()
    runtime.login.mockImplementation(async (account: string) => success({
      accessToken: `test-session-${account}-123456789`, expiresAt: '2099-09-05T12:00:00Z',
    }))
    runtime.exchangeMiniCode.mockResolvedValue(success({accessToken: 'fresh-mini-session-123456789', expiresAt: '2099-09-05T12:00:00Z'}))
    runtime.getRuntime.mockResolvedValue(success({status: 'available', version: '1210-01', gameVersion: '12.1.0', build: '69299', sourceCommit: 'runtime-source', runtimeRevision: 'current'}))
    runtime.navigate.mockResolvedValue({})
    runtime.createJob.mockResolvedValue(success({id: 'submitted-job', status: 'queued', attempts: [], result: null}))
    runtime.logout.mockResolvedValue(success({ loggedOut: true }))
    runtime.me.mockResolvedValue(success({connected: true, displayName: '当前测试账号'}))
    runtime.avatarGet.mockResolvedValue(success({avatarDataUrl: null}))
    runtime.modal.mockResolvedValue({confirm: false})
    runtime.createChat.mockResolvedValue(success({ id: 'new-conversation', title: '新对话', updatedAt: '2026-09-07T03:00:00Z' }))
    runtime.getChat.mockResolvedValue(success({ id: 'new-conversation', title: '新对话', updatedAt: '2026-09-07T03:00:00Z', messages: [] }))
    runtime.stream.mockReturnValue({ abort: vi.fn() })
    runtime.createSnapshot.mockResolvedValue(success({ id: 'snapshot-a', readiness: 'READY_FOR_SIMC', provider: 'raiderio', revision: 'r1', provenance: { sourceRevision: 'r1' }, missingFields: [], blockers: [] }))
    runtime.listChat.mockResolvedValue(success({ items: [], nextCursor: null }))
    runtime.listJobs.mockResolvedValue(success({ items: [], nextCursor: null }))
    runtime.getJob.mockResolvedValue(success({
      id: runtime.params.id, status: 'succeeded', attempts: [], result: null,
    }))
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  async function render(content: ReactNode) {
    await act(async () => root.render(content))
  }

  async function mountSignedOut(Page: ComponentType) {
    await render(createElement(Page))
    await act(async () => {
      runtime.load.forEach((callback) => callback(runtime.params))
      runtime.show.forEach((callback) => callback())
    })
    expect(container.querySelector('[data-test-login]')).not.toBeNull()
  }

  async function click(label: string) {
    const button = Array.from(container.querySelectorAll('button')).find((item) => item.textContent === label || item.getAttribute('aria-label') === label)
    expect(button, `Missing button ${label}`).toBeDefined()
    await act(async () => button!.click())
  }

  it.each([
    ['Chat', ChickenbroPage, runtime.listChat],
    ['SimC history', SimcTasksPage, runtime.listJobs],
  ] as const)('loads %s immediately after login without another page-show event', async (_, Page, list) => {
    await mountSignedOut(Page)
    expect(list).not.toHaveBeenCalled()
    await click('Enter A')
    expect(list).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      auth: { kind: 'mini', accessToken: 'test-session-A-123456789' },
    }))
    await click('退出 / 切换账号')
    await click('Enter B')
    expect(list).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({
      auth: { kind: 'mini', accessToken: 'test-session-B-123456789' },
    }))
  })

  async function input(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value')!.set!
      setter.call(element, value)
      element.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  it('opens only help from the formal Mini menu and preserves the logged-in page', async () => {
    vi.stubGlobal('__WOW_TEST_LOGIN__', false)
    runtime.storage.set(MINI_SESSION_KEY, {accessToken: 'formal-mini-session-123456789', expiresAt: '2099-09-05T12:00:00Z'})
    await render(createElement(ChickenbroPage))
    await act(async () => {runtime.show.forEach(callback => callback())})
    const composer = container.querySelector('textarea')!
    runtime.actionSheet.mockResolvedValueOnce({tapIndex: 0})
    await click('更多')
    expect(runtime.actionSheet).toHaveBeenLastCalledWith({itemList: ['FAQ · 常见问题', '更新日志']})
    expect(container.textContent).toContain('FAQ · 常见问题')
    expect(container.textContent).not.toMatch(/账号与外观|退出登录/)
    expect(runtime.me).not.toHaveBeenCalled()
    expect(runtime.logout).not.toHaveBeenCalled()
    await click('关闭帮助')
    expect(container.querySelector('textarea')).toBe(composer)
  })

  it('opens help before login and returns to the same chat draft after reading updates', async () => {
    await mountSignedOut(ChickenbroPage)
    runtime.actionSheet.mockResolvedValueOnce({ tapIndex: 0 })
    await click('更多')
    await click('账号记录')
    expect(container.textContent).toContain('Web 和小程序的记录会同步吗？')
    await click('关闭帮助')
    await click('Enter A')
    expect(container.textContent).not.toMatch(/更换头像|更新头像|长按文字可复制/)
    expect(container.querySelector('img')).not.toBeNull()
    const composer = container.querySelector('textarea')!
    await input(composer, '这段草稿要保留')
    const historyReads = runtime.listChat.mock.calls.length
    runtime.actionSheet.mockRejectedValueOnce({ errMsg: 'showActionSheet:fail cancel' })
    await click('更多')
    expect(composer.value).toBe('这段草稿要保留')
    runtime.actionSheet.mockResolvedValueOnce({ tapIndex: 1 })
    await click('更多')
    expect(container.textContent).toContain('小程序移动端交互优化')
    expect(container.textContent).toContain('Web 导航与帮助入口')
    await click('关闭帮助')
    expect(container.querySelector('textarea')).toBe(composer)
    expect(composer.value).toBe('这段草稿要保留')
    expect(runtime.listChat).toHaveBeenCalledTimes(historyReads)
  })

  it('keeps the SimC source draft on returning without a more menu', async () => {
    await mountSignedOut(SimcPage)
    await click('Enter A')
    const source = container.querySelector('textarea')!
    await input(source, 'https://raider.io/characters/us/illidan/example')
    expect(Array.from(container.querySelectorAll('button')).some(button => button.textContent === '更多')).toBe(false)
    await act(async () => runtime.show.forEach(callback => callback()))
    expect(container.querySelector('textarea')).toBe(source)
    expect(source.value).toBe('https://raider.io/characters/us/illidan/example')
  })

  it('sends a first draft through a created conversation and prevents duplicate sends while replying', async () => {
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    let composer = container.querySelector('textarea')!
    await input(composer, '帮我分析战斗')
    await click('发送')
    await act(async () => runtime.stream.mock.calls[0]?.[2].onEvent({
      type: 'started', conversationId: 'new-conversation', requestId: 'request', runId: 'run', sequence: 1,
    }))
    // Sending replaces the native editor; inspect the current input, not the detached node.
    composer = container.querySelector('textarea')!
    expect(composer.value).toBe('')
    expect(container.textContent).toContain('正在思考')
    expect(container.textContent).toContain('帮我分析战斗')
    expect(runtime.createChat).toHaveBeenCalledTimes(1)
    expect(runtime.stream).toHaveBeenCalledWith('new-conversation', expect.objectContaining({ content: '帮我分析战斗' }), expect.anything())
    await input(composer, '下一条草稿')
    const replying = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === '回复中')!
    expect(replying.disabled).toBe(true)
    await act(async () => replying.click())
    expect(runtime.stream).toHaveBeenCalledTimes(1)
    expect(composer.value).toBe('下一条草稿')
  })

  it('locks the composer while a new conversation is being created', async () => {
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    let finish!: (value: unknown) => void
    runtime.createChat.mockReturnValue(new Promise((resolve) => { finish = resolve }))
    await click('＋ 新对话')
    const composer = container.querySelector('textarea')!
    expect(composer.disabled).toBe(true)
    await act(async () => finish(success({ id: 'new-conversation', title: '新对话', updatedAt: '2026-09-07T03:00:00Z' })))
    expect(composer.disabled).toBe(false)
  })

  it('continues scrolling when reply deltas arrive faster than the scroll interval', async () => {
    vi.useFakeTimers()
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    await input(container.querySelector('textarea')!, '连续回复')
    await click('发送')
    await act(async () => { await vi.advanceTimersByTimeAsync(100) })
    const scroll = container.querySelector('[data-scroll-target]')!
    const before = scroll.getAttribute('data-scroll-target')
    const onEvent = runtime.stream.mock.calls[0]![2].onEvent
    const event = { conversationId: 'new-conversation', requestId: 'request-1', runId: 'run-1' }
    await act(async () => onEvent({ ...event, sequence: 1, type: 'started' }))
    for (let sequence = 2; sequence <= 4; sequence++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(40)
        onEvent({ ...event, sequence, type: 'delta', text: '增量' })
      })
    }
    await act(async () => { await vi.advanceTimersByTimeAsync(30) })
    expect(scroll.getAttribute('data-scroll-target')).not.toBe(before)
    expect(container.textContent).toContain('增量增量增量')
  })

  it('shrinks the Mini viewport with the keyboard and restores it when dismissed', async () => {
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    const frame = container.firstElementChild as HTMLElement
    expect(frame.style.height).toBe('720px')
    await act(async () => runtime.keyboard.forEach((callback) => callback({ height: 300 })))
    expect(frame.style.height).toBe('420px')
    await act(async () => runtime.keyboard.forEach((callback) => callback({ height: 0 })))
    expect(frame.style.height).toBe('720px')
  })

  it('requires rereading an edited source and validates simulation parameter bounds', async () => {
    await mountSignedOut(SimcPage)
    await click('Enter A')
    const source = container.querySelector('textarea')!
    await input(source, 'https://raider.io/characters/us/illidan/example')
    await click('读取角色')
    const submit = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === '开始模拟')!
    expect(submit.disabled).toBe(false)
    await input(source, 'https://raider.io/characters/us/illidan/another')
    expect(submit.disabled).toBe(true)
    expect(container.textContent).toContain('链接已更改')
    await input(source, 'https://raider.io/characters/us/illidan/example')
    await input(container.querySelectorAll('input')[0]!, '21')
    expect(submit.disabled).toBe(true)
    await act(async () => submit.click())
    expect(runtime.createJob).not.toHaveBeenCalled()
  })

  it('submits the complete mobile scenario with Mini auth and workbench payloads', async () => {
    await mountSignedOut(SimcPage)
    await click('Enter A')
    expect(container.textContent).toContain('Simc版本：1210-01')
    await input(container.querySelector('textarea')!, 'https://raider.io/characters/us/illidan/example')
    await click('读取角色')
    expect(runtime.createSnapshot).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({workbench: true, auth: {kind: 'mini', accessToken: 'test-session-A-123456789'}}))
    await click('精度与增益')
    const values = { desiredTargets: '3', maxTime: '180', varyCombatLength: '10', iterations: '1000', targetError: '0.5' }
    for (const [name, value] of Object.entries(values)) await input(container.querySelector(`[data-field="${name}"]`)!, value)
    const picker = container.querySelector<HTMLSelectElement>('[data-field="fightStyle"]')!
    await act(async () => { picker.value = '2'; picker.dispatchEvent(new Event('change', {bubbles: true})) })
    await act(async () => container.querySelector<HTMLInputElement>('[data-field="bloodlust"]')!.click())
    await act(async () => container.querySelector<HTMLInputElement>('[data-field="raidBuffs"]')!.click())
    await click('开始模拟')
    expect(runtime.createJob).toHaveBeenCalledWith({snapshotId: 'snapshot-a', scenario: {
      fightStyle: 'LightMovement', desiredTargets: 3, iterations: 1000, maxTime: 180, varyCombatLength: 0.1, targetError: 0.5, raidBuffs: false, bloodlust: false,
    }}, expect.objectContaining({workbench: true, localizedReport: true, auth: {kind: 'mini', accessToken: 'test-session-A-123456789'}}))
    expect(runtime.navigate).toHaveBeenCalledWith({url: '/pages/simc/task-detail?id=submitted-job'})
  })

  it('requires an available engine and validates hidden advanced values before submission', async () => {
    runtime.getRuntime.mockResolvedValue(success({status: 'unavailable'}))
    await mountSignedOut(SimcPage)
    await click('Enter A')
    await input(container.querySelector('textarea')!, 'https://raider.io/characters/us/illidan/example')
    await click('读取角色')
    const submit = () => Array.from(container.querySelectorAll('button')).find(b => b.textContent === '开始模拟')!
    expect(submit().disabled).toBe(true)
    runtime.getRuntime.mockResolvedValue(success({status: 'available', version: '1210-01'}))
    await click('重试引擎')
    expect(submit().disabled).toBe(false)
    await click('精度与增益')
    await input(container.querySelector('[data-field="targetError"]')!, '6')
    await click('精度与增益')
    expect(submit().disabled).toBe(true)
    expect(container.textContent).toContain('目标误差')
    expect(runtime.createJob).not.toHaveBeenCalled()
  })

  it('restores submission after a production Mini session is rejected and renewed', async () => {
    vi.stubGlobal('__WOW_TEST_LOGIN__', false)
    runtime.storage.set(MINI_SESSION_KEY, {accessToken: 'old-mini-session-123456789', expiresAt: '2099-09-05T12:00:00Z'})
    await render(createElement(SimcPage))
    await act(async () => runtime.show.forEach(callback => callback()))
    await input(container.querySelector('textarea')!, 'https://raider.io/characters/us/illidan/example')
    await click('读取角色')
    runtime.createJob.mockResolvedValueOnce({fromFallback: true, problemCode: 'AUTH_REQUIRED', httpStatus: 401, payload: null, error: 'Authentication required'})
    await click('开始模拟')
    expect(container.querySelector('[data-simc-phase="signed_out"]')).not.toBeNull()
    await click('重新登录')
    const submit = Array.from(container.querySelectorAll('button')).find(button => button.textContent === '开始模拟')!
    expect(submit.disabled).toBe(false)
    expect(container.querySelector('[data-simc-phase="signed_out"]')).toBeNull()
    await click('开始模拟')
    expect(runtime.createJob).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({auth: {kind: 'mini', accessToken: 'fresh-mini-session-123456789'}}))
    expect(runtime.navigate).toHaveBeenCalledWith({url: '/pages/simc/task-detail?id=submitted-job'})
  })

  it('renews a rejected production Mini session when retrying the engine', async () => {
    vi.stubGlobal('__WOW_TEST_LOGIN__', false)
    runtime.storage.set(MINI_SESSION_KEY, {accessToken: 'old-mini-session-123456789', expiresAt: '2099-09-05T12:00:00Z'})
    runtime.getRuntime.mockImplementation(async ({auth}: {auth: {accessToken: string}}) => auth.accessToken === 'old-mini-session-123456789'
      ? {fromFallback: true, problemCode: 'AUTH_REQUIRED', httpStatus: 401, payload: null, error: 'Authentication required'}
      : success({status: 'available', version: '1210-01'}))
    await render(createElement(SimcPage))
    expect(container.querySelector('[data-runtime-status="unknown"]')).not.toBeNull()
    await click('重试引擎')
    expect(container.querySelector('[data-runtime-status="available"]')).not.toBeNull()
    expect(new MiniSessionStore(wowApi.webAuth).createAuthContext()).toEqual({kind: 'mini', accessToken: 'fresh-mini-session-123456789'})
  })

  it('filters mobile task cards while preserving character and metric summaries', async () => {
    runtime.listJobs.mockResolvedValue(success({items: [
      {id: 'done', status: 'succeeded', updatedAt: '2026-09-07T01:00:00Z', character: {name: '完成角色', className: 'shaman', specialization: 'elemental'}, scenario: {fightStyle: 'LightMovement', desiredTargets: 3}, metric: {name: 'dps', value: 123456}},
      {id: 'waiting', status: 'queued', updatedAt: '2026-09-07T01:00:00Z', character: {name: '排队角色', className: 'mage', specialization: 'fire'}},
    ], nextCursor: 'next'}))
    await mountSignedOut(SimcTasksPage)
    await click('Enter A')
    expect(container.textContent).toContain('完成角色')
    expect(container.textContent).toContain('123,456')
    const filter = container.querySelector<HTMLSelectElement>('[data-field="taskStatus"]')!
    await act(async () => { filter.value = '1'; filter.dispatchEvent(new Event('change', {bubbles: true})) })
    expect(container.textContent).not.toContain('完成角色')
    expect(container.textContent).toContain('排队角色')
    await click('加载更多')
    expect(runtime.listJobs).toHaveBeenLastCalledWith({cursor: 'next', limit: 20}, expect.objectContaining({workbench: true}))
  })

  it('renders complete mobile report groups, keeps sorted names with metrics and degrades old results honestly', async () => {
    const actor = {name: '报告角色', className: 'shaman', specialization: 'elemental', talents: 'talent-code'}
    const report = {schemaVersion: 2, actor, engine: {version: '1210-01', gameVersion: '12.1.0', build: '69299'}, metric: {error: 3}, statistics: {iterations: 1000, fightLengthSeconds: 180, elapsedSeconds: 5},
      abilities: [{name: 'same', amount: 10, portion: 10, executions: 1, critPercent: 2}, {name: 'same', amount: 90, portion: 90, executions: 8, critPercent: 20}],
      buffs: [{name: 'bloodlust', uptime: 15}], resources: [{name: 'mana', gained: 30, lost: 20}], attributes: [{name: 'haste_pct', value: 22}], gear: [{slot: 'head', itemId: 123, itemLevel: 200}],
      localization: {status: 'complete', catalogRevision: 'names', abilities: [{text: '低贡献技能'}, {text: '高贡献技能'}], buffs: [{text: '嗜血'}]}}
    runtime.getJob.mockResolvedValue(success({id: runtime.params.id, status: 'succeeded', attempts: [], character: actor, scenario: {fightStyle: 'LightMovement', desiredTargets: 3, maxTime: 180, iterations: 1000, varyCombatLength: .1, targetError: .5, raidBuffs: false, bloodlust: true}, result: {id: 'result', metricName: 'dps', metricValue: 123456, report}}))
    await mountSignedOut(SimcTaskDetailPage)
    await click('Enter A')
    expect(container.textContent).toContain('误差 ± 3')
    expect(container.textContent).toContain('Simc版本：1210-01')
    expect(container.textContent).toContain('平均战斗时长')
    const rows = container.querySelectorAll('[data-ability]')
    expect(rows[0]?.textContent).toContain('高贡献技能')
    expect(rows[1]?.textContent).toContain('低贡献技能')
    for (const group of ['增益覆盖', '资源', '属性', '装备与天赋', '本次模拟配置']) await click(group)
    for (const value of ['嗜血', '法力', '获得 30', '消耗 20', '22%', '头部', 'talent-code', '少量移动', '180 秒']) expect(container.textContent).toContain(value)
    runtime.getJob.mockResolvedValue(success({id: runtime.params.id, status: 'succeeded', attempts: [], result: {metricName: 'dps', metricValue: 99, metricError: 2, report: null}}))
    await click('刷新状态')
    expect(container.textContent).toContain('历史任务仅保存了结果摘要')
    expect(container.textContent).toContain('误差 ± 2')
    expect(container.textContent).not.toContain('高贡献技能')
  })

  it('preserves the original detail route when login mounts the page after onLoad', async () => {
    await mountSignedOut(SimcTaskDetailPage)
    await click('Enter A')
    expect(runtime.getJob).toHaveBeenCalledWith(runtime.params.id, {
      auth: { kind: 'mini', accessToken: 'test-session-A-123456789' },
      workbench: true, localizedReport: true,
    })
    expect(container.textContent).toContain(runtime.params.id)
    await click('查看运行详情')
    expect(container.textContent).toContain(runtime.params.id)
  })

  it('shows credential entry when another store logs out without navigation', async () => {
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    expect(container.querySelector('[data-test-login]')).toBeNull()
    const otherPageSession = new MiniSessionStore(wowApi.webAuth)
    await act(async () => otherPageSession.logout())
    expect(container.querySelector('[data-test-login]')).not.toBeNull()
    expect(container.querySelector('[data-chat-phase]')).toBeNull()
  })

  it('returns to credential entry when the business API rejects the session', async () => {
    runtime.listChat.mockResolvedValue({
      fromFallback: true, problemCode: 'AUTH_REQUIRED', httpStatus: 401,
      payload: { items: [], nextCursor: null }, error: 'Authentication required',
    })
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    // Trigger a later page show too: this exercises 401 recovery independently of mount loading.
    await act(async () => runtime.show.forEach((callback) => callback()))
    expect(runtime.listChat).toHaveBeenCalled()
    expect(container.querySelector('[data-test-login]')).not.toBeNull()
    expect(new MiniSessionStore(wowApi.webAuth).getValid()).toBeNull()
  })

  it('removes the business page when its session expires in the foreground', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-05T12:00:00Z'))
    runtime.login.mockResolvedValue(success({
      accessToken: 'test-session-A-123456789', expiresAt: '2026-09-05T12:00:02Z',
    }))
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    expect(container.querySelector('[data-chat-phase]')).not.toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(61000) })
    expect(container.querySelector('[data-test-login]')).not.toBeNull()
    expect(container.querySelector('[data-chat-phase]')).toBeNull()
  })
})
