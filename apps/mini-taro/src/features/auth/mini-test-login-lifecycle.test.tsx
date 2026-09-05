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
    navigateTo: vi.fn(), navigateBack: vi.fn(), login: vi.fn(),
  } }
})

vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => {
    const allowed = Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id'].includes(key) || key.startsWith('data-')))
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
    chat: { list: runtime.listChat },
    simc: { listJobs: runtime.listJobs, getJob: runtime.getJob },
  },
}))

vi.mock('./TestLoginForm', async () => {
  const { createElement: element } = await import('react')
  return { default: ({ onLogin }: { onLogin: (account: 'A' | 'B', credential: string) => Promise<void> }) =>
    element('div', { 'data-test-login': true }, ...(['A', 'B'] as const).map((account) =>
      element('button', { key: account, onClick: () => void onLogin(account, 'test-only-' + 'x'.repeat(32)) }, `Enter ${account}`))) }
})

import ChickenbroPage from '../../pages/chickenbro'
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
    runtime.show.clear()
    runtime.load.clear()
    vi.clearAllMocks()
    runtime.login.mockImplementation(async (account: string) => success({
      accessToken: `test-session-${account}-123456789`, expiresAt: '2099-09-05T12:00:00Z',
    }))
    runtime.logout.mockResolvedValue(success({ loggedOut: true }))
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

  it('preserves the original detail route when login mounts the page after onLoad', async () => {
    await mountSignedOut(SimcTaskDetailPage)
    await click('Enter A')
    expect(runtime.getJob).toHaveBeenCalledWith(runtime.params.id, {
      auth: { kind: 'mini', accessToken: 'test-session-A-123456789' },
    })
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
