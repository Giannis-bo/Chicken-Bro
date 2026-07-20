import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storageKey } from '@wow-mini/domain'

import { configuredApiBaseUrl, createTaroTransport, DEV_API_BASE_URL } from './transport'
import type { StorageAdapter } from './storage'

const taro = vi.hoisted(() => ({
  request: vi.fn(),
  getAccountInfoSync: vi.fn(() => ({ miniProgram: { envVersion: 'develop' } })),
  getEnv: vi.fn(() => 'WEAPP'),
  ENV_TYPE: { WEB: 'WEB', WEAPP: 'WEAPP' },
}))

vi.mock('@tarojs/taro', () => ({ default: taro }))

class MemoryStorage implements StorageAdapter {
  private readonly values = new Map<string, unknown>()

  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

describe('Taro transport parity', () => {
  beforeEach(() => {
    taro.request.mockReset()
    taro.request.mockResolvedValue({ statusCode: 200, data: { ok: true } })
    taro.getEnv.mockReturnValue('WEAPP')
    taro.getAccountInfoSync.mockReset()
    taro.getAccountInfoSync.mockReturnValue({ miniProgram: { envVersion: 'develop' } })
  })

  it('fails closed before an authenticated request can use insecure HTTP', async () => {
    const storage = new MemoryStorage()
    storage.set(storageKey('auth.token'), 'secret')
    const transport = createTaroTransport({ storage, resolveBaseUrl: () => 'http://example.test' })
    const result = await transport.request('/private', {
      auth: true,
      fallback: () => ({ ok: false }),
    })
    expect(result.fromFallback).toBe(true)
    expect(result.error).toContain('insecure')
    expect(taro.request).not.toHaveBeenCalled()
  })

  it('allows only an explicitly guest-capable simulator endpoint over development HTTP', async () => {
    const transport = createTaroTransport({ storage: new MemoryStorage(), resolveBaseUrl: () => 'http://example.test' })
    const result = await transport.requestEndpoint('simulator.tasks', '/api/simulator/tasks?guest=1', {
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({ tasks: [] }),
      validate: () => true,
    })
    expect(result.fromFallback).toBe(false)
    expect(taro.request).toHaveBeenCalledOnce()
  })

  it('falls back locally when a required HTTPS endpoint has no auth token', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://example.test',
    })
    const result = await transport.requestEndpoint('templates.list', '/api/me/build-templates?type=gear', {
      fallback: () => ({ schemaVersion: 1, templates: [] }),
      validate: () => true,
    })

    expect(result).toMatchObject({
      payload: { schemaVersion: 1, templates: [] },
      fromFallback: true,
      error: 'missing auth token',
    })
    expect(taro.request).not.toHaveBeenCalled()
  })

  it('preserves the news transport omission of analytics headers', async () => {
    const transport = createTaroTransport({ storage: new MemoryStorage(), resolveBaseUrl: () => 'https://example.test' })
    await transport.requestEndpoint('news.home', '/api/news/home', {
      fallback: () => ({ ok: false }),
      validate: () => true,
    })
    const request = taro.request.mock.calls[0]?.[0] as { header?: Record<string, string> }
    expect(request.header?.['X-Wow-Client-Id']).toBeUndefined()
  })

  it('attaches analytics identity and HTTPS bearer auth for shared transport', async () => {
    const storage = new MemoryStorage()
    storage.set(storageKey('auth.token'), 'secret')
    const transport = createTaroTransport({ storage, resolveBaseUrl: () => 'https://example.test' })
    await transport.request('/private', {
      auth: true,
      fallback: () => ({ ok: false }),
      validate: () => true,
    })
    const request = taro.request.mock.calls[0]?.[0] as { header?: Record<string, string> }
    expect(request.header?.['Authorization']).toBe('Bearer secret')
    expect(request.header?.['X-Wow-Client-Id']).toMatch(/^mp-/)
    expect(request.header?.['X-Wow-Session-Id']).toMatch(/^session-/)
  })

  it('resolves the development base URL without a Node process global', () => {
    let baseUrl = ''
    vi.stubGlobal('process', undefined)
    try {
      baseUrl = configuredApiBaseUrl(new MemoryStorage())
    } finally {
      vi.unstubAllGlobals()
    }
    expect(baseUrl).toBe(DEV_API_BASE_URL)
  })

  it('uses a same-origin H5 proxy without weakening insecure auth checks', async () => {
    taro.getEnv.mockReturnValue('WEB')
    vi.stubGlobal('window', { location: { origin: 'http://127.0.0.1:10086' } })
    vi.stubGlobal('document', {})
    try {
      const storage = new MemoryStorage()
      storage.set(storageKey('auth.token'), 'secret')
      expect(configuredApiBaseUrl(storage)).toBe('http://127.0.0.1:10086/wow-api')
      const transport = createTaroTransport({ storage })
      const result = await transport.request('/private', {
        auth: true,
        fallback: () => ({ ok: false }),
      })
      expect(result.fromFallback).toBe(true)
      expect(result.error).toContain('insecure')
      expect(taro.request).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('does not mistake mini-program DOM shims for the H5 runtime', () => {
    vi.stubGlobal('window', { location: { origin: 'https://taro.com' } })
    vi.stubGlobal('document', {})
    try {
      taro.getEnv.mockReturnValue('WEAPP')
      expect(configuredApiBaseUrl(new MemoryStorage())).toBe(DEV_API_BASE_URL)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it.each(['release', 'trial'])('ignores stored overrides in the %s mini-program and accepts only a named HTTPS build origin', (envVersion) => {
    const storage = new MemoryStorage()
    storage.set(storageKey('api.base'), 'http://124.223.51.33')
    taro.getAccountInfoSync.mockReturnValue({ miniProgram: { envVersion } })
    vi.stubGlobal('__WOW_BACKEND_API_BASE_URL__', 'https://api.chickenbro.cloud')
    try {
      expect(configuredApiBaseUrl(storage)).toBe('https://api.chickenbro.cloud')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it.each([
    'http://api.chickenbro.cloud',
    'https://124.223.51.33',
    'not-a-url',
  ])('fails closed in release when the build origin is not a named HTTPS URL: %s', (origin) => {
    const storage = new MemoryStorage()
    storage.set(storageKey('api.base'), 'https://stored.example.test')
    taro.getAccountInfoSync.mockReturnValue({ miniProgram: { envVersion: 'release' } })
    vi.stubGlobal('__WOW_BACKEND_API_BASE_URL__', origin)
    try {
      expect(configuredApiBaseUrl(storage)).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('fails closed when the mini-program environment cannot be identified', () => {
    const storage = new MemoryStorage()
    storage.set(storageKey('api.base'), DEV_API_BASE_URL)
    taro.getAccountInfoSync.mockImplementation(() => { throw new Error('account info unavailable') })
    vi.stubGlobal('__WOW_BACKEND_API_BASE_URL__', 'https://api.chickenbro.cloud')
    try {
      expect(configuredApiBaseUrl(storage)).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('preserves structured problem envelopes and HTTP status for canonical gear conflicts', async () => {
    const envelope = {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'request-conflict',
      status: 'conflict',
      releaseContext: { manifestRevision: 'manifest-2' },
      data: {},
      problems: [{ code: 'REVISION_CONFLICT' }],
    }
    taro.request.mockResolvedValue({ statusCode: 409, data: envelope })
    const transport = createTaroTransport({ storage: new MemoryStorage(), resolveBaseUrl: () => 'https://example.test' })
    const result = await transport.request('/api/websim/gear/resolve', {
      method: 'POST',
      data: {},
      responseMode: 'structured-problem',
      fallback: () => ({}),
      validate: (value) => value === envelope,
    })

    expect(result).toMatchObject({
      payload: envelope,
      fromFallback: false,
      httpStatus: 409,
      transportError: '',
      offline: false,
    })
  })

  it('marks structured network failures as offline without promoting fallback payloads', async () => {
    taro.request.mockRejectedValue(new Error('network down'))
    const transport = createTaroTransport({ storage: new MemoryStorage(), resolveBaseUrl: () => 'https://example.test' })
    const result = await transport.request('/api/websim/gear/stat-snapshots', {
      method: 'POST',
      data: {},
      responseMode: 'structured-problem',
      fallback: () => ({ status: 'unavailable' }),
    })

    expect(result).toMatchObject({ fromFallback: true, httpStatus: 0, offline: true })
    expect(result.transportError).toContain('network down')
  })
})
