// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { WebAuthClient } from '@wow-mini/api-client'

vi.mock('@wow-mini/api-client', () => ({
  readWebCsrfCookie: () => 'csrf-value',
  wowApi: { webAuth: {} },
}))
vi.mock('./WebShell', () => ({ default: ({ accountLabel, avatarUrl, onLogout }: { accountLabel: string; avatarUrl?: string; onLogout: () => void }) => createElement('div', {}, accountLabel, avatarUrl ? createElement('img', { src: avatarUrl }) : null, createElement('button', { onClick: onLogout }, '退出登录')) }))
vi.mock('../features/auth/TestLoginForm', () => ({ default: () => createElement('div', {}, '测试账号入口') }))
vi.mock('@tarojs/components', async () => { const { createElement: h } = await import('react'); return { View: (p: object) => h('div', p), Text: (p: object) => h('span', p), Button: (p: object) => h('button', p) } })

import WebApp from './WebApp'

const ok = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
const signedOut = { payload: null, fromFallback: true, error: '', httpStatus: 401, problemCode: 'AUTH_REQUIRED' }
const officialUrl = 'https://graph.qq.com/oauth2.0/authorize?client_id=1905584243&state=abc'

describe('Web QQ login home', () => {
  let container: HTMLDivElement; let root: Root; let auth: WebAuthClient; let navigate: (url: string) => void
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); vi.stubGlobal('__WOW_TEST_LOGIN__', false)
    document.cookie = '__Host-chickenbro-csrf=csrf-value; path=/'
    window.history.replaceState(null, '', '/')
    auth = {
      me: vi.fn().mockResolvedValue(signedOut), createQqLogin: vi.fn().mockResolvedValue(ok({ authorizationUrl: officialUrl, requestId: 'r1' })),
      logout: vi.fn().mockResolvedValue(ok({ loggedOut: true })), loginTestWeb: vi.fn(),
    }
    navigate = vi.fn<(url: string) => void>(); container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  })
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals() })
  const render = async () => { await act(async () => root.render(createElement(WebApp, { authClient: auth, navigateToProvider: navigate }))) }
  const click = async (label: string) => { const button = Array.from(container.querySelectorAll('button')).find(node => node.textContent === label); expect(button).toBeDefined(); await act(async () => button!.click()) }

  it('shows one explicit QQ action without creating or polling a QR', async () => {
    await render()
    expect(container.querySelector('aside[aria-label="QQ 登录"]')).not.toBeNull()
    expect(container.textContent).toContain('QQ登录')
    expect(auth.createQqLogin).not.toHaveBeenCalled()
    expect(Object.hasOwn(auth, 'createWebLoginSession')).toBe(false)
    const logo = container.querySelector('img[src*="Connect_logo_1.png"]')
    expect(logo?.getAttribute('referrerpolicy')).toBe('no-referrer')
  })

  it('redirects only after a validated official QQ response', async () => { await render(); await click('QQ登录'); expect(navigate).toHaveBeenCalledWith(officialUrl) })

  it('blocks an invalid provider URL and offers an explicit retry', async () => {
    vi.mocked(auth.createQqLogin).mockResolvedValueOnce(ok({ authorizationUrl: 'https://evil.example/oauth2.0/authorize' }) as never)
    await render(); await click('QQ登录')
    expect(navigate).not.toHaveBeenCalled(); expect(container.textContent).toContain('QQ 登录入口暂不可用'); expect(container.textContent).toContain('QQ登录')
  })

  it('shows a fixed cancelled callback message, clears only that query and does not auto-login', async () => {
    window.history.replaceState(null, '', '/simc?keep=1&loginError=QQ_LOGIN_CANCELLED')
    await render()
    expect(container.textContent).toContain('你已取消 QQ 授权，可以重新登录。')
    expect(window.location.pathname + window.location.search).toBe('/simc?keep=1')
    expect(auth.createQqLogin).not.toHaveBeenCalled()
  })

  it('loads an authenticated QQ account and its allowlisted avatar, then logs out', async () => {
    vi.mocked(auth.me).mockResolvedValue(ok({ connected: true, displayName: 'QQ 队长', avatarUrl: 'https://q.qlogo.cn/headimg_dl?dst_uin=1' }) as never)
    await render()
    expect(container.textContent).toContain('QQ 队长'); expect(container.querySelector('img')?.src).toContain('q.qlogo.cn')
    await click('退出登录'); expect(auth.logout).toHaveBeenCalledOnce(); expect(container.textContent).toContain('QQ登录')
  })

  it('retains the nonproduction test login path', async () => { vi.stubGlobal('__WOW_TEST_LOGIN__', true); await render(); expect(container.textContent).toContain('测试账号入口'); expect(auth.createQqLogin).not.toHaveBeenCalled() })
})
