import { describe, expect, it, vi } from 'vitest'

import { SimulatorClient } from './simulator'
import type { StorageAdapter } from './storage'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

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

  it('reads the backend-owned SimC options contract without local option fallbacks', async () => {
    const payload = {
      contractRevision: 'simc-options-v1',
      status: 'ready',
      races: {
        status: 'supported',
        defaultKey: 'zandalari_troll',
        supportedKeys: ['zandalari_troll'],
        defaultByClass: { mage: 'zandalari_troll' },
      },
      scenarios: [{
        key: 'backend_raid', label: 'Backend raid', fightStyle: 'Patchwerk',
        targets: 7, durationSeconds: 417, status: 'supported',
      }],
      preparation: {
        schemaRevision: 'simc-preparation-v1',
        status: 'ready',
        rows: [{
          key: 'backend_rule', category: 'backend', label: 'Backend rule',
          defaultState: 'enabled', evidenceState: 'verified', overrideSupported: true,
        }],
      },
    }
    const calls: Array<{ endpoint: string; path: string }> = []
    const requestEndpoint = vi.fn(async <T>(
      endpoint: string,
      path: string,
      options: Omit<RequestOptions<T>, 'method'>,
    ): Promise<ApiResult<T>> => {
      calls.push({ endpoint, path })
      return options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
    })
    const client = new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage())
    const options = (client as unknown as {
      options?: () => Promise<ApiResult<typeof payload>>
    }).options

    expect(options).toBeTypeOf('function')
    if (!options) return
    const result = await options.call(client)

    expect(calls).toEqual([{
      endpoint: 'simulator.simcOptions',
      path: '/api/simulator/simc/options',
    }])
    expect(result.fromFallback).toBe(false)
    expect(result.payload.scenarios[0]).toMatchObject({ targets: 7, durationSeconds: 417 })
    expect(result.payload.preparation.rows[0]?.overrideSupported).toBe(true)
  })
})
