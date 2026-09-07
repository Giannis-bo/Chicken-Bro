// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@wow-mini/api-client', () => ({
  wowApi: { webAuth: {} }, readWebCsrfCookie: () => 'test-csrf',
}))
vi.mock('./WebShell', () => ({ default: ({ onLogout }: { onLogout: () => void }) => createElement('div', {}, '已进入对话与模拟', createElement('button', { onClick: onLogout }, '退出登录')) }))
vi.mock('../features/auth/TestLoginForm', () => ({ default: () => createElement('div', {}, '测试账号入口') }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag,
    Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id', 'src', 'alt'].includes(key)
      || key.startsWith('data-') || key.startsWith('aria-'))))
  return { View: host('div'), Text: host('span'), Button: host('button'), Image: host('img') }
})

import WebApp from './WebApp'
import type { WebAuthClient } from '@wow-mini/api-client'

const success = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
const signedOut = { payload: null, fromFallback: true, error: '', httpStatus: 401, problemCode: 'AUTH_REQUIRED' }
const qrDataUrl = 'data:image/jpeg;base64,/9j/2Q=='
const sessionId = '12345678-1234-4234-8234-123456789012'

describe('unauthenticated Web home', () => {
  let container: HTMLDivElement
  let root: Root
  let auth: WebAuthClient
  let expiresAt: string

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    vi.stubGlobal('__WOW_TEST_LOGIN__', false)
    vi.useFakeTimers()
    sessionStorage.clear()
    expiresAt = new Date(Date.now() + 300000).toISOString()
    auth = {
      me: vi.fn().mockResolvedValue(signedOut),
      createWebLoginSession: vi.fn().mockResolvedValue(success({ sessionId, expiresAt, qrDataUrl })),
      statusWebLoginSession: vi.fn().mockResolvedValue(success({ status: 'pending', expiresAt })),
      exchangeWebLoginSession: vi.fn().mockResolvedValue(success({ authenticated: true })),
      cancelWebLoginSession: vi.fn().mockResolvedValue(success({ status: 'cancelled', expiresAt })),
      logout: vi.fn(), loginTestMini: vi.fn(), loginTestWeb: vi.fn(),
      exchangeMiniCode: vi.fn(), confirmMiniWebLogin: vi.fn(),
    }
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
  const render = async () => { await act(async () => root.render(createElement(WebApp, { authClient: auth }))) }
  const click = async (label: string) => {
    const button = Array.from(container.querySelectorAll('button')).find(item => item.textContent === label)
    expect(button).toBeDefined()
    await act(async () => button!.click())
  }

  it('shows the public home and automatically creates one complete QR in the login region', async () => {
    await render()
    expect(auth.createWebLoginSession).toHaveBeenCalledTimes(1)
    expect(container.querySelector('h1')).not.toBeNull()
    expect(document.documentElement.classList.contains('web-login-fixed')).toBe(true)
    expect(container.querySelector('footer')?.textContent).toBe('Powered by Lighthouse&Codex')
    expect(container.textContent).not.toContain('魔兽世界 · 对话与模拟')
    expect(container.textContent).not.toMatch(/有问题，找鸡哥|有想法，模拟一下|为每一次更好的战斗/)
    expect(container.querySelector('aside[aria-label="微信扫码登录"] img')?.getAttribute('src')).toBe(qrDataUrl)
    expect(container.textContent).not.toMatch(/Cookie|Bearer|token|内部用户/)
    await act(async () => vi.advanceTimersByTimeAsync(4000))
    expect(auth.createWebLoginSession).toHaveBeenCalledTimes(1)
  })

  it('returns to the redesigned home with a new complete QR after logout', async () => {
    vi.mocked(auth.me).mockResolvedValue(success({ connected: true, displayName: '队长' }) as never)
    vi.mocked(auth.logout).mockResolvedValue(success({ loggedOut: true }) as never)
    await render()
    await click('退出登录')
    expect(auth.logout).toHaveBeenCalledOnce()
    expect(container.querySelector('h1')?.textContent).toContain('先问鸡哥')
    expect(container.querySelector('aside[aria-label="微信扫码登录"] img')?.getAttribute('src')).toBe(qrDataUrl)
    expect(auth.createWebLoginSession).toHaveBeenCalledOnce()
    expect(container.textContent).not.toMatch(/Cookie|Bearer|内部用户|已进入对话与模拟/)
  })

  it('restores document scrolling when the home unmounts', async () => {
    await render()
    expect(document.body.classList.contains('web-login-fixed')).toBe(true)
    await act(async () => root.render(null))
    expect(document.body.classList.contains('web-login-fixed')).toBe(false)
    expect(document.documentElement.classList.contains('web-login-fixed')).toBe(false)
  })

  it('does not create a QR for an authenticated visitor or expose the public home', async () => {
    vi.mocked(auth.me).mockResolvedValue(success({ connected: true, displayName: '队长' }) as never)
    await render()
    expect(auth.createWebLoginSession).not.toHaveBeenCalled()
    expect(container.textContent).toContain('已进入对话与模拟')
    expect(document.documentElement.classList.contains('web-login-fixed')).toBe(false)
    expect(container.querySelector('aside')).toBeNull()
  })

  it('lets cancellation stop the flow without automatically issuing another QR', async () => {
    await render()
    await click('取消登录')
    await act(async () => vi.advanceTimersByTimeAsync(6000))
    expect(auth.cancelWebLoginSession).toHaveBeenCalledTimes(1)
    expect(auth.createWebLoginSession).toHaveBeenCalledTimes(1)
    expect(container.querySelector('aside img')).toBeNull()
    await click('重新扫码')
    expect(auth.createWebLoginSession).toHaveBeenCalledTimes(2)
  })

  it('removes an expired QR and offers an explicit refresh', async () => {
    await render()
    await act(async () => vi.advanceTimersByTimeAsync(301000))
    expect(container.querySelector('aside img')).toBeNull()
    expect(container.textContent).toContain('二维码已过期')
    await click('刷新二维码')
    expect(auth.createWebLoginSession).toHaveBeenCalledTimes(2)
  })

  it('keeps the home visible during provider failure and retries on request', async () => {
    vi.mocked(auth.createWebLoginSession).mockResolvedValueOnce({
      ...signedOut, httpStatus: 502, problemCode: 'WECHAT_PROVIDER_UNAVAILABLE',
    } as never)
    await render()
    expect(container.querySelector('h1')).not.toBeNull()
    expect(container.textContent).toContain('微信服务暂不可用')
    await click('重新扫码')
    expect(container.querySelector('aside img')).not.toBeNull()
  })

  it('reuses the request identity after an ambiguous network failure and hides transport details', async () => {
    vi.mocked(auth.createWebLoginSession).mockResolvedValueOnce({
      payload: null, fromFallback: true, error: 'internal transport diagnostic',
    } as never)
    await render()
    expect(container.textContent).toContain('二维码生成失败，请稍后重试')
    expect(container.textContent).not.toContain('internal transport diagnostic')
    const firstAttempt = vi.mocked(auth.createWebLoginSession).mock.calls[0]
    await click('重新扫码')
    expect(vi.mocked(auth.createWebLoginSession).mock.calls[1]).toEqual(firstAttempt)
  })

  it('exchanges only after Mini confirmation and then enters the authenticated workspace', async () => {
    await render()
    expect(auth.exchangeWebLoginSession).not.toHaveBeenCalled()
    vi.mocked(auth.statusWebLoginSession).mockResolvedValue(success({ status: 'confirmed', expiresAt }) as never)
    vi.mocked(auth.me).mockResolvedValue(success({ connected: true, displayName: '队长' }) as never)
    await act(async () => vi.advanceTimersByTimeAsync(1500))
    expect(auth.exchangeWebLoginSession).toHaveBeenCalledTimes(1)
    expect(container.textContent).toContain('已进入对话与模拟')
  })

  it('keeps the explicit test account build on its existing login path', async () => {
    vi.stubGlobal('__WOW_TEST_LOGIN__', true)
    await render()
    expect(auth.createWebLoginSession).not.toHaveBeenCalled()
    expect(container.textContent).toContain('测试账号入口')
  })
})
