import { describe, expect, it, vi } from 'vitest'

import { SimulatorClient } from './simulator'
import type { StorageAdapter } from './storage'
import type { ApiTransport, RequestOptions } from './transport'

const taro = vi.hoisted(() => ({
  getStorageSync: vi.fn(() => ''),
  setStorageSync: vi.fn(),
  removeStorageSync: vi.fn(),
}))

vi.mock('@tarojs/taro', () => ({ default: taro }))

class MemoryStorage implements StorageAdapter {
  private readonly values = new Map<string, unknown>()

  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

describe('SimulatorClient task contract', () => {
  it('treats a backend task:null response as a verified empty result', async () => {
    const requestEndpoint = vi.fn(async <T>(
      _endpointId: string,
      _path: string,
      options: Omit<RequestOptions<T>, 'method'>,
    ) => {
      const payload = { task: null }
      const valid = options.validate?.(payload) ?? false
      return valid
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
    })
    const transport = { requestEndpoint } as unknown as ApiTransport
    const client = new SimulatorClient(transport, new MemoryStorage())

    const result = await client.task('missing-task')

    expect(result).toEqual({ payload: { task: null }, fromFallback: false, error: '' })
  })
})
