import { describe, expect, it, vi } from 'vitest'

import type { EndpointId } from '@wow-mini/domain'

import { TemplateRepository } from './templates'
import type { StorageAdapter } from './storage'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

vi.mock('@tarojs/taro', () => ({
  default: {
    getStorageSync: () => '',
    setStorageSync: () => undefined,
    removeStorageSync: () => undefined,
  },
}))

class MemoryStorage implements StorageAdapter {
  private readonly values = new Map<string, unknown>()
  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

class FallbackTransport implements ApiTransport {
  async request<T>(_path: string, options: RequestOptions<T>): Promise<ApiResult<T>> {
    return { payload: options.fallback(), fromFallback: true, error: 'offline' }
  }

  async requestEndpoint<T>(
    _endpointId: EndpointId,
    _path: string,
    options: Omit<RequestOptions<T>, 'method'>,
  ): Promise<ApiResult<T>> {
    return { payload: options.fallback(), fromFallback: true, error: 'offline' }
  }
}

describe('local-first template repository', () => {
  it('persists a valid template and keeps it visibly local', () => {
    const repository = new TemplateRepository(new FallbackTransport(), new MemoryStorage(), { now: () => 1000, random: () => 0.5 })
    const template = repository.saveLocal({ type: 'talent', rawString: 'verified-import', title: '测试天赋' })
    expect(template?.trust.level).toBe('local_only')
    expect(repository.list('talent')).toHaveLength(1)
  })

  it('rejects a template without a raw payload', () => {
    const repository = new TemplateRepository(new FallbackTransport(), new MemoryStorage())
    expect(repository.saveLocal({ type: 'gear', rawString: '' })).toBeNull()
  })

  it('returns local templates through the remote fallback envelope', async () => {
    const repository = new TemplateRepository(new FallbackTransport(), new MemoryStorage())
    repository.saveLocal({ type: 'gear', rawString: '{"head":{"itemId":1}}' })
    const result = await repository.fetch('gear')
    expect(result.fromFallback).toBe(true)
    expect(result.payload.templates).toHaveLength(1)
    expect(result.payload.templates[0]?.remote).toBe(false)
  })
})
