import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ApiResult, StorageAdapter, WebAuthClient } from '@wow-mini/api-client'
import type { LogoutResponse, MiniExchangeResponse } from '@wow-mini/domain'

import { MINI_SESSION_KEY, MiniSessionStore } from './mini-session'


const taro = vi.hoisted(() => ({ login: vi.fn() }))

vi.mock('@tarojs/taro', () => ({ default: taro }))

class MemoryStorage implements StorageAdapter {
  readonly values = new Map<string, unknown>()

  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

function success<T>(payload: T): ApiResult<T> {
  return { payload, fromFallback: false, error: '', httpStatus: 200 }
}

function authClient(
  exchangeMiniCode: WebAuthClient['exchangeMiniCode'],
  logout: WebAuthClient['logout'] = vi.fn(async () => success<LogoutResponse>({ loggedOut: true })),
): Pick<WebAuthClient, 'exchangeMiniCode' | 'logout'> {
  return { exchangeMiniCode, logout }
}

describe('MiniSessionStore', () => {
  beforeEach(() => {
    taro.login.mockReset()
    taro.login.mockResolvedValue({ code: 'wx-login-code' })
  })

  it('exchanges wx.login and stores only the bounded Mini session', async () => {
    const storage = new MemoryStorage()
    const exchange = vi.fn(async () => success<MiniExchangeResponse>({
      accessToken: 'mini-access-token-123456',
      expiresAt: '2026-09-03T12:30:00.000Z',
      requestId: 'private-request-id',
    }))
    const sessions = new MiniSessionStore(authClient(exchange), storage, {
      now: () => Date.parse('2026-09-03T12:00:00.000Z'),
    })

    const session = await sessions.login()

    expect(exchange).toHaveBeenCalledWith('wx-login-code')
    expect(session).toEqual({
      accessToken: 'mini-access-token-123456',
      expiresAt: '2026-09-03T12:30:00.000Z',
    })
    expect(storage.values.get(MINI_SESSION_KEY)).toEqual(session)
    expect(JSON.stringify(storage.values.get(MINI_SESSION_KEY))).not.toMatch(/requestId|openid|session_key|csrf|cookie/iu)
    expect(sessions.createAuthContext()).toEqual({
      kind: 'mini',
      accessToken: 'mini-access-token-123456',
    })
  })

  it.each([
    { accessToken: 'mini-access-token-123456', expiresAt: '2026-09-03T11:59:59.000Z' },
    { accessToken: 'short', expiresAt: '2026-09-03T12:30:00.000Z' },
    { accessToken: 'mini-access-token-123456', expiresAt: 'not-a-date' },
    {
      accessToken: 'mini-access-token-123456',
      expiresAt: '2026-09-03T12:30:00.000Z',
      openid: 'must-not-survive',
    },
  ])('rejects expired or malformed local state: $accessToken / $expiresAt', (stored) => {
    const storage = new MemoryStorage()
    storage.set(MINI_SESSION_KEY, stored)
    const sessions = new MiniSessionStore(
      authClient(vi.fn()),
      storage,
      { now: () => Date.parse('2026-09-03T12:00:00.000Z') },
    )

    expect(sessions.getValid()).toBeNull()
    expect(storage.values.has(MINI_SESSION_KEY)).toBe(false)
    expect(() => sessions.createAuthContext()).toThrow('MINI_SESSION_REQUIRED')
  })

  it('does not persist a fallback or malformed exchange response', async () => {
    const storage = new MemoryStorage()
    const exchange = vi.fn(async () => ({
      payload: { accessToken: 'fallback-token', expiresAt: '' },
      fromFallback: true,
      error: 'network down',
      problemCode: 'WECHAT_PROVIDER_UNAVAILABLE',
    }))
    const sessions = new MiniSessionStore(authClient(exchange), storage)

    await expect(sessions.login()).rejects.toThrow('WECHAT_PROVIDER_UNAVAILABLE')
    expect(storage.values.has(MINI_SESSION_KEY)).toBe(false)
  })

  it('revokes only the current Mini bearer and always clears local state', async () => {
    const storage = new MemoryStorage()
    storage.set(MINI_SESSION_KEY, {
      accessToken: 'mini-access-token-123456',
      expiresAt: '2026-09-03T12:30:00.000Z',
    })
    const logout = vi.fn(async () => success<LogoutResponse>({ loggedOut: true }))
    const sessions = new MiniSessionStore(
      authClient(vi.fn(), logout),
      storage,
      { now: () => Date.parse('2026-09-03T12:00:00.000Z') },
    )

    await sessions.logout()

    expect(logout).toHaveBeenCalledWith({
      kind: 'mini',
      accessToken: 'mini-access-token-123456',
    })
    expect(storage.values.has(MINI_SESSION_KEY)).toBe(false)
  })
})
