import { describe, expect, it, vi } from 'vitest'

import type { EndpointId } from '@wow-mini/domain'

import { AuthClient } from './auth'
import type { StorageAdapter } from './storage'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

vi.mock('@tarojs/taro', () => ({ default: {} }))

class MemoryStorage implements StorageAdapter {
  private readonly values = new Map<string, unknown>()
  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

class UnusedTransport implements ApiTransport {
  async request<T>(_path: string, options: RequestOptions<T>): Promise<ApiResult<T>> {
    return { payload: options.fallback(), fromFallback: true, error: 'unused' }
  }

  async requestEndpoint<T>(
    _endpointId: EndpointId,
    _path: string,
    options: Omit<RequestOptions<T>, 'method'>,
  ): Promise<ApiResult<T>> {
    return { payload: options.fallback(), fromFallback: true, error: 'unused' }
  }
}

describe('auth identity trust boundary', () => {
  it('keeps backend identity only while an authenticated session is active', () => {
    const storage = new MemoryStorage()
    const client = new AuthClient(new UnusedTransport(), storage)
    client.persist({
      accessToken: 'token',
      expiresAt: Date.now() + 60_000,
      user: { openid: 'server-openid', nickname: '服务端昵称' },
    })

    expect(client.profile()).toMatchObject({ openid: 'server-openid', nickname: '服务端昵称' })
    client.clear()
    expect(client.profile()).toEqual({ nickname: '服务端昵称' })
  })

  it('never persists a caller-supplied server identity as local profile data', () => {
    const client = new AuthClient(new UnusedTransport(), new MemoryStorage())

    expect(client.saveLocalProfile({ openid: 'unverified-openid', nickname: '本地昵称' }))
      .toEqual({ nickname: '本地昵称' })
    expect(client.profile()).toEqual({ nickname: '本地昵称' })
  })
})
