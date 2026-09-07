// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { beforeEach, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ load: undefined as undefined | ((p: {scene: string}) => void), confirm: vi.fn(), navigate: vi.fn(), storage: new Map<string, unknown>() }))
vi.mock('@tarojs/taro', () => ({ default: { login: async () => ({code: 'code'}), switchTab: api.navigate }, useLoad: (fn: typeof api.load) => { api.load = fn } }))
vi.mock('@wow-mini/api-client', () => ({ taroStorage: { get: (key: string) => api.storage.get(key), set: (key: string, value: unknown) => api.storage.set(key, value), remove: (key: string) => api.storage.delete(key) }, wowApi: { webAuth: { exchangeMiniCode: async () => ({fromFallback: false, payload: {accessToken: 'mini-session-valid-token', expiresAt: '2099-09-07T12:00:00Z'}}), confirmMiniWebLogin: api.confirm } } }))
vi.mock('@tarojs/components', async () => {
  const {createElement: h} = await import('react')
  return { Image: (p: Record<string, unknown>) => h('img', {src: p['src'] as string}), View: (p: Record<string, unknown>) => h('div', {}, p['children'] as never), Text: (p: Record<string, unknown>) => h('span', {}, p['children'] as never), Button: (p: Record<string, unknown>) => h('button', {disabled: !!p['disabled'], onClick: p['onClick'] as () => void}, p['children'] as never) }
})
vi.mock('../../features/auth/MiniAccountAvatar', () => ({default: () => createElement('button', {'data-avatar': true}, '设置头像')}))
import WebLoginConfirmPage from './web-login-confirm'
import { MINI_SESSION_KEY, MiniSessionStore } from '../../features/auth/mini-session'
import { wowApi } from '@wow-mini/api-client'
beforeEach(() => {
  vi.clearAllMocks(); api.storage.clear(); api.navigate.mockReset(); api.navigate.mockResolvedValue({})
})
it('confirms login without exposing account avatar controls', async () => {
  Object.assign(globalThis, {IS_REACT_ACT_ENVIRONMENT: true})
  api.confirm.mockResolvedValue({fromFallback: false})
  const node = document.createElement('div'); document.body.append(node)
  const root = createRoot(node)
  try {
    await act(async () => root.render(createElement(WebLoginConfirmPage)))
    expect(node.querySelector('[data-avatar]')).toBeNull()
    await act(async () => api.load?.({scene: 'opaque-scene'}))
    expect(node.querySelector('[data-avatar]')).toBeNull()
    expect(node.textContent).not.toContain('可跳过')
    expect(node.textContent).not.toMatch(/跨设备登录确认|本页不会展示|WEB BRIDGE/)
    expect(node.querySelector('img')).not.toBeNull()
    expect(api.confirm).not.toHaveBeenCalled()
    const button = Array.from(node.querySelectorAll('button')).find(x => x.textContent === '确认登录')!
    await act(async () => button.click())
    expect(api.confirm).toHaveBeenCalledWith('opaque-scene', 'mini-session-valid-token')
    expect(api.navigate).toHaveBeenCalledWith({url: '/pages/chickenbro/index'})
    expect(new MiniSessionStore(wowApi.webAuth).createAuthContext()).toEqual({kind: 'mini', accessToken: 'mini-session-valid-token'})
    expect(node.querySelectorAll('[data-avatar]')).toHaveLength(0)
  } finally { await act(async () => root.unmount()); node.remove() }
})

it('does not navigate when confirmation fails', async () => {
  api.confirm.mockResolvedValue({fromFallback: true, error: 'expired', problemCode: 'WEB_LOGIN_EXPIRED'})
  const node = document.createElement('div'); document.body.append(node); const root = createRoot(node)
  try {
    await act(async () => root.render(createElement(WebLoginConfirmPage)))
    await act(async () => api.load?.({scene: 'opaque-scene'}))
    await act(async () => Array.from(node.querySelectorAll('button')).find(x => x.textContent === '确认登录')!.click())
    expect(api.navigate).not.toHaveBeenCalled()
    expect(node.textContent).toContain('二维码已过期')
  } finally { await act(async () => root.unmount()); node.remove() }
})
it('persists Mini session before navigating and retries navigation without confirming twice', async () => {
  api.confirm.mockResolvedValue({fromFallback: false})
  api.navigate.mockImplementationOnce(async () => {
    expect(api.storage.has(MINI_SESSION_KEY)).toBe(true)
    throw new Error('navigation failed')
  })
  const node = document.createElement('div'); document.body.append(node); const root = createRoot(node)
  try {
    await act(async () => root.render(createElement(WebLoginConfirmPage)))
    await act(async () => api.load?.({scene: 'opaque-scene'}))
    await act(async () => Array.from(node.querySelectorAll('button')).find(x => x.textContent === '确认登录')!.click())
    expect(node.textContent).toContain('登录成功')
    const retry = Array.from(node.querySelectorAll('button')).find(x => x.textContent === '进入小程序')!
    expect(retry).toBeDefined()
    await act(async () => retry.click())
    expect(api.navigate).toHaveBeenCalledTimes(2)
    expect(api.confirm).toHaveBeenCalledTimes(1)
  } finally { await act(async () => root.unmount()); node.remove() }
})
