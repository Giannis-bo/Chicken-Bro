import { beforeEach, describe, expect, it, vi } from 'vitest'

import { storageKey } from '@wow-mini/domain'

import { NdjsonDecoder, configuredApiBaseUrl, createTaroTransport, DEV_API_BASE_URL } from './transport'
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

  it('passes explicit Cookie credentials and resolves the v2 Web base independently of the legacy proxy', async () => {
    taro.getEnv.mockReturnValue('WEB')
    vi.stubGlobal('window', { location: { origin: 'https://www.chickenbro.cloud' } })
    vi.stubGlobal('document', {})
    try {
      const transport = createTaroTransport({
        storage: new MemoryStorage(),
        resolveBaseUrl: () => 'https://www.chickenbro.cloud/wow-api',
        resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
      })
      await transport.request('/api/v2/me', {
        auth: false,
        baseUrl: 'web-auth',
        credentials: 'include',
        responseMode: 'structured-problem',
        fallback: () => ({ connected: false }),
        validate: () => true,
      })

      const request = taro.request.mock.calls[0]?.[0] as {
        url?: string
        credentials?: string
      }
      expect(request.url).toBe('https://www.chickenbro.cloud/api/v2/me')
      expect(request.credentials).toBe('include')
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

  it('decodes UTF-8 NDJSON only after complete lines arrive across arbitrary chunks', () => {
    const decoder = new NdjsonDecoder()
    const encoder = new TextEncoder()
    const first = encoder.encode('{"type":"delta","text":"你').buffer
    const second = encoder.encode('好"}\n{"type":"status","stage":"generating"}\n').buffer

    expect(decoder.push(first)).toEqual([])
    expect(decoder.push(second)).toEqual([
      { type: 'delta', text: '你好' },
      { type: 'status', stage: 'generating' },
    ])
    expect(decoder.finish()).toEqual([])
  })

  it('aborts and reports one failure when a chunk contains malformed NDJSON', async () => {
    let receive: ((value: { data: ArrayBuffer }) => void) | undefined
    const abort = vi.fn()
    const task = Object.assign(Promise.resolve({ statusCode: 200, data: null }), {
      abort,
      onChunkReceived: vi.fn((listener) => { receive = listener }),
    })
    taro.request.mockReturnValue(task)
    const failures: string[] = []
    const transport = createTaroTransport({ storage: new MemoryStorage(), resolveBaseUrl: () => 'https://example.test' })
    const requestStreamEndpoint = transport.requestStreamEndpoint
    expect(requestStreamEndpoint).toBeTypeOf('function')
    if (!requestStreamEndpoint) throw new Error('stream transport must be present')
    requestStreamEndpoint('chickenbro.messages.stream', '/api/chickenbro/messages/stream', {
      data: { message: '测试' },
      auth: true,
      allowInsecureGuestRequest: true,
      onEvent: () => { throw new Error('must not emit malformed event') },
      onFailure: (error) => failures.push(error),
    })

    receive?.({ data: new TextEncoder().encode('{not-json}\n').buffer })
    await Promise.resolve()

    expect(abort).toHaveBeenCalledOnce()
    expect(failures).toEqual(['malformed stream payload'])
  })

  it('uses browser fetch streaming for H5 SSE and keeps it same-origin', async () => {
    taro.getEnv.mockReturnValue('WEB')
    vi.stubGlobal('window', { location: { origin: 'https://www.chickenbro.cloud' } })
    vi.stubGlobal('document', {})
    const reader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('data: {"type":"started","sequence":1}\n\n'),
        })
        .mockResolvedValueOnce({ done: true, value: undefined }),
      cancel: vi.fn(),
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    })
    vi.stubGlobal('fetch', fetchMock)
    try {
      const transport = createTaroTransport({
        storage: new MemoryStorage(),
        resolveBaseUrl: () => 'https://www.chickenbro.cloud/wow-api',
        resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
      })
      const events: unknown[] = []
      const failures: string[] = []
      const task = transport.requestSse
      expect(task).toBeTypeOf('function')
      if (!task) throw new Error('SSE transport must be present')
      task('/api/v2/prototype/stream', {
        method: 'POST',
        baseUrl: 'web-auth',
        data: { content: 'hello' },
        header: { 'X-Prototype-Session': 'a'.repeat(64) },
        onEvent: (event) => events.push(event),
        onFailure: (error) => failures.push(error),
      })
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(fetchMock).toHaveBeenCalledWith(
        'https://www.chickenbro.cloud/api/v2/prototype/stream',
        expect.objectContaining({
          method: 'POST',
          credentials: 'omit',
          body: JSON.stringify({ content: 'hello' }),
        }),
      )
      expect(events).toEqual([{ type: 'started', sequence: 1 }])
      expect(failures).toEqual([])
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('includes the formal Web Cookie on SSE only when explicitly requested', async () => {
    taro.getEnv.mockReturnValue('WEB')
    vi.stubGlobal('window', { location: { origin: 'https://www.chickenbro.cloud' } })
    vi.stubGlobal('document', {})
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => ({ read: vi.fn().mockResolvedValue({ done: true }) }) },
    })
    vi.stubGlobal('fetch', fetchMock)
    try {
      const transport = createTaroTransport({
        storage: new MemoryStorage(),
        resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
      })
      const requestSse = transport.requestSse
      expect(requestSse).toBeTypeOf('function')
      if (!requestSse) throw new Error('SSE transport must be present')

      requestSse('/api/v2/chat/conversations/id/messages/stream', {
        method: 'POST',
        baseUrl: 'web-auth',
        credentials: 'include',
        data: { content: 'hello' },
        onEvent: () => {},
        onFailure: () => {},
      })
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(fetchMock).toHaveBeenCalledWith(
        'https://www.chickenbro.cloud/api/v2/chat/conversations/id/messages/stream',
        expect.objectContaining({ credentials: 'include' }),
      )
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
