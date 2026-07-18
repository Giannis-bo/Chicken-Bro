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

  it('fails closed on incompatible, duplicate, or unbounded simc-options-v1 facts', async () => {
    const valid = {
      contractRevision: 'simc-options-v1', status: 'ready',
      races: {
        status: 'supported', defaultKey: 'human', supportedKeys: ['human', 'troll'],
        defaultByClass: { mage: 'human' },
      },
      scenarios: [{
        key: 'single', label: 'Single', fightStyle: 'Patchwerk', targets: 1,
        durationSeconds: 300, status: 'supported',
      }],
      preparation: {
        schemaRevision: 'simc-preparation-v1', status: 'ready',
        rows: [{
          key: 'optimal_raid', category: 'raid', label: 'Raid', defaultState: 'disabled',
          evidenceState: 'verified', overrideSupported: true,
        }],
      },
    }
    const invalid: readonly unknown[] = [
      { ...valid, status: 'partial' },
      { ...valid, races: { ...valid.races, status: 'ready' } },
      { ...valid, races: { ...valid.races, supportedKeys: [] } },
      { ...valid, races: { ...valid.races, supportedKeys: ['human', 'human'] } },
      { ...valid, races: { ...valid.races, defaultKey: 'orc' } },
      { ...valid, races: { ...valid.races, defaultByClass: { mage: 'orc' } } },
      { ...valid, scenarios: [{ ...valid.scenarios[0], key: '' }] },
      { ...valid, scenarios: [valid.scenarios[0], { ...valid.scenarios[0] }] },
      { ...valid, scenarios: [{ ...valid.scenarios[0], targets: 1.5 }] },
      { ...valid, scenarios: [{ ...valid.scenarios[0], durationSeconds: 0 }] },
      { ...valid, preparation: { ...valid.preparation, schemaRevision: 'simc-preparation-v0' } },
      { ...valid, preparation: { ...valid.preparation, status: 'partial' } },
      { ...valid, preparation: { ...valid.preparation, rows: [] } },
      { ...valid, preparation: { ...valid.preparation, rows: [valid.preparation.rows[0], { ...valid.preparation.rows[0] }] } },
      { ...valid, preparation: { ...valid.preparation, rows: [{ ...valid.preparation.rows[0], defaultState: 'automatic' }] } },
      { ...valid, preparation: { ...valid.preparation, rows: [{ ...valid.preparation.rows[0], evidenceState: 'ready' }] } },
    ]

    const results = await Promise.all(invalid.map(async (payload) => {
      const requestEndpoint = async <T>(
        _endpoint: string,
        _path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      return new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage()).options()
    }))

    expect(results.every((result) => result.fromFallback)).toBe(true)
    expect(results.every((result) => (
      result.payload.status === 'blocked'
      && result.payload.races.supportedKeys.length === 0
      && result.payload.scenarios.length === 0
      && result.payload.preparation.rows.length === 0
    ))).toBe(true)
  })
})
