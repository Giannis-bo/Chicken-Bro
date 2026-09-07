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
  login: vi.fn(), logout: vi.fn(),
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
    navigateTo: vi.fn(), navigateBack: vi.fn(), login: vi.fn(),
  } }
})

vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => {
    const allowed = Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id', 'style', 'placeholder'].includes(key) || key.startsWith('data-')))
    if (props['scrollIntoView']) allowed['data-scroll-target'] = props['scrollIntoView']
    if (props['onInput']) allowed['onInput'] = (event: { currentTarget: { value: string } }) => (props['onInput'] as (event: unknown) => void)({ detail: { value: event.currentTarget.value } })
    if ('value' in props) { allowed['value'] = props['value']; allowed['onChange'] = () => undefined }
    return element(tag, allowed)
  }
  return { View: host('div'), Text: host('span'), Button: host('button'),
    ScrollView: host('div'), Textarea: host('textarea'), Input: host('input') }
})

vi.mock('@wow-mini/api-client', () => ({
  taroStorage: {
    get: (key: string) => runtime.storage.get(key),
    set: (key: string, value: unknown) => { runtime.storage.set(key, value) },
    remove: (key: string) => { runtime.storage.delete(key) },
  },
  wowApi: {
    webAuth: { loginTestMini: runtime.login, logout: runtime.logout },
    chat: { list: runtime.listChat, create: runtime.createChat, get: runtime.getChat, streamMessage: runtime.stream },
    simc: { listJobs: runtime.listJobs, getJob: runtime.getJob, createSnapshot: runtime.createSnapshot, createJob: runtime.createJob },
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
import { MiniSessionStore } from './mini-session'

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
    runtime.logout.mockResolvedValue(success({ loggedOut: true }))
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
    const button = Array.from(container.querySelectorAll('button')).find((item) => item.textContent === label)
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
    expect(list).toHaveBeenCalledWith(expect.anything(), {
      auth: { kind: 'mini', accessToken: 'test-session-A-123456789' },
    })
    await click('退出 / 切换账号')
    await click('Enter B')
    expect(list).toHaveBeenLastCalledWith(expect.anything(), {
      auth: { kind: 'mini', accessToken: 'test-session-B-123456789' },
    })
  })

  async function input(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value')!.set!
      setter.call(element, value)
      element.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  it('opens help before login and returns to the same chat draft after reading updates', async () => {
    await mountSignedOut(ChickenbroPage)
    await click('FAQ')
    expect(container.textContent).toContain('Web 和小程序的记录会同步吗？')
    await click('关闭帮助')
    await click('Enter A')
    const composer = container.querySelector('textarea')!
    await input(composer, '这段草稿要保留')
    const historyReads = runtime.listChat.mock.calls.length
    await click('更新日志')
    expect(container.textContent).toContain('小程序移动端交互优化')
    expect(container.textContent).toContain('Web 导航与帮助入口')
    await click('关闭帮助')
    expect(container.querySelector('textarea')).toBe(composer)
    expect(composer.value).toBe('这段草稿要保留')
    expect(runtime.listChat).toHaveBeenCalledTimes(historyReads)
  })

  it('provides FAQ from the SimC page without changing the source draft', async () => {
    await mountSignedOut(SimcPage)
    await click('Enter A')
    const source = container.querySelector('textarea')!
    await input(source, 'https://raider.io/characters/us/illidan/example')
    await click('FAQ')
    expect(container.textContent).toContain('模拟支持哪些角色来源？')
    await click('关闭帮助')
    expect(container.querySelector('textarea')).toBe(source)
    expect(source.value).toBe('https://raider.io/characters/us/illidan/example')
  })

  it('sends a first draft through a created conversation and prevents duplicate sends while replying', async () => {
    await mountSignedOut(ChickenbroPage)
    await click('Enter A')
    const composer = container.querySelector('textarea')!
    await input(composer, '帮我分析战斗')
    await click('发送')
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

  it('preserves the original detail route when login mounts the page after onLoad', async () => {
    await mountSignedOut(SimcTaskDetailPage)
    await click('Enter A')
    expect(runtime.getJob).toHaveBeenCalledWith(runtime.params.id, {
      auth: { kind: 'mini', accessToken: 'test-session-A-123456789' },
      workbench: true, localizedReport: true,
    })
    expect(container.textContent).not.toContain(runtime.params.id)
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
