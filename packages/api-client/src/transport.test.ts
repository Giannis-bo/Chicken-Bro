import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  configuredApiBaseUrl,
  createTaroTransport,
  DEV_API_BASE_URL,
  SseDecoder,
} from './transport'
import type { RequestOptions } from './transport'
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

function encoded(value: string): ArrayBuffer {
  const bytes = new TextEncoder().encode(value)
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
}

describe('formal Taro transport', () => {
  beforeEach(() => {
    taro.request.mockReset()
    taro.request.mockResolvedValue({ statusCode: 200, data: { ok: true } })
    taro.getEnv.mockReturnValue('WEAPP')
    taro.getAccountInfoSync.mockReset()
    taro.getAccountInfoSync.mockReturnValue({ miniProgram: { envVersion: 'develop' } })
  })

  it('derives Mini Bearer credentials over HTTPS without legacy analytics identity', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })

    const result = await transport.request('/api/v2/chat/conversations', {
      auth: { kind: 'mini', accessToken: 'mini-token' },
      fallback: () => ({ ok: false }),
      validate: () => true,
    })

    const request = taro.request.mock.calls[0]?.[0] as {
      credentials?: string
      header?: Record<string, string>
      url?: string
    }
    expect(result.fromFallback).toBe(false)
    expect(request.url).toBe('https://api.chickenbro.cloud/api/v2/chat/conversations')
    expect(request.credentials).toBe('omit')
    expect(request.header).toEqual({ Authorization: 'Bearer mini-token' })
    expect(request.header?.['X-Wow-Client-Id']).toBeUndefined()
    expect(request.header?.['X-Wow-Session-Id']).toBeUndefined()
  })

  it('derives Web Cookie credentials and adds CSRF only to mutations', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
    })

    await transport.request('/api/v2/chat/conversations', {
      auth: { kind: 'web', csrfToken: 'web-csrf' },
      fallback: () => ({ items: [] }),
      validate: () => true,
    })
    await transport.request('/api/v2/chat/conversations', {
      method: 'POST',
      auth: { kind: 'web', csrfToken: 'web-csrf' },
      header: { 'Idempotency-Key': 'write-one' },
      fallback: () => ({ id: '' }),
      validate: () => true,
    })

    const read = taro.request.mock.calls[0]?.[0] as {
      credentials?: string
      header?: Record<string, string>
      url?: string
    }
    const write = taro.request.mock.calls[1]?.[0] as {
      credentials?: string
      header?: Record<string, string>
      url?: string
    }
    expect(read).toMatchObject({
      url: 'https://www.chickenbro.cloud/api/v2/chat/conversations',
      credentials: 'include',
      header: {},
    })
    expect(write.credentials).toBe('include')
    expect(write.header).toEqual({
      'Idempotency-Key': 'write-one',
      'X-CSRF-Token': 'web-csrf',
    })
    expect(write.header?.['Authorization']).toBeUndefined()
  })

  it('rejects authenticated HTTP before a request can leave the client', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'http://example.test',
    })

    const result = await transport.request('/api/v2/simc/jobs', {
      auth: { kind: 'mini', accessToken: 'mini-token' },
      fallback: () => ({ items: [] }),
    })

    expect(result.fromFallback).toBe(true)
    expect(result.error).toContain('insecure')
    expect(taro.request).not.toHaveBeenCalled()
  })

  it.each(['ftp://example.test', 'not-a-url'])('rejects every non-HTTPS authenticated origin: %s', async (origin) => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => origin,
    })

    const result = await transport.request('/api/v2/simc/jobs', {
      auth: { kind: 'mini', accessToken: 'mini-token' },
      fallback: () => ({ items: [] }),
    })

    expect(result.fromFallback).toBe(true)
    expect(result.error).toContain('insecure')
    expect(taro.request).not.toHaveBeenCalled()
  })

  it('rejects explicit credential headers when an auth context is present', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })

    const result = await transport.request('/api/v2/chat/conversations', {
      auth: { kind: 'mini', accessToken: 'mini-token' },
      header: { Authorization: 'Bearer shadow-token' },
      fallback: () => ({ items: [] }),
    })

    expect(result.fromFallback).toBe(true)
    expect(result.error).toContain('explicit credential headers')
    expect(taro.request).not.toHaveBeenCalled()
  })

  it('fails closed when a caller omits the formal auth context at runtime', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })
    const missingAuth = {
      fallback: () => ({ items: [] }),
    } as unknown as RequestOptions<{ items: unknown[] }>

    const result = await transport.request('/api/v2/chat/conversations', missingAuth)

    expect(result.fromFallback).toBe(true)
    expect(result.error).toContain('auth context is required')
    expect(taro.request).not.toHaveBeenCalled()
  })

  it('allows public auth only on exact formal readiness and login routes', async () => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
      resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
    })

    const readiness = await transport.request('/api/v2/health/readiness', {
      auth: { kind: 'public' },
      fallback: () => ({ ready: false }),
      validate: () => true,
    })
    const login = await transport.request('/api/v2/auth/wechat/web/login-sessions', {
      method: 'POST',
      auth: { kind: 'public' },
      baseUrl: 'web-auth',
      credentials: 'include',
      fallback: () => ({ sessionId: '' }),
      validate: () => true,
    })
    const rejected = await transport.request('/api/v2/chat/conversations', {
      auth: { kind: 'public' },
      fallback: () => ({ items: [] }),
    })

    expect(readiness.fromFallback).toBe(false)
    expect(login.fromFallback).toBe(false)
    expect(rejected.fromFallback).toBe(true)
    expect(rejected.error).toContain('public auth context')
    expect(taro.request).toHaveBeenCalledTimes(2)
  })

  it('uses only the formal local API-base storage key in development', () => {
    const storage = new MemoryStorage()
    storage.set('wow_backend_api_base_url', 'https://local.example.test')
    storage.set('wow_api_base_url', 'https://legacy.example.test')

    expect(configuredApiBaseUrl(storage)).toBe('https://local.example.test')
  })

  it('defaults to the development origin without a Node process global', () => {
    vi.stubGlobal('process', undefined)
    try {
      expect(configuredApiBaseUrl(new MemoryStorage())).toBe(DEV_API_BASE_URL)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it.each(['release', 'trial'])('ignores local overrides in %s and accepts only a named HTTPS build origin', (envVersion) => {
    const storage = new MemoryStorage()
    storage.set('wow_backend_api_base_url', 'http://124.223.51.33')
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
    'https://api.chickenbro.cloud/path',
    'not-a-url',
  ])('fails closed in release when the build origin is not an HTTPS named origin: %s', (origin) => {
    taro.getAccountInfoSync.mockReturnValue({ miniProgram: { envVersion: 'release' } })
    vi.stubGlobal('__WOW_BACKEND_API_BASE_URL__', origin)
    try {
      expect(configuredApiBaseUrl(new MemoryStorage())).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('fails closed when the mini-program environment cannot be identified', () => {
    taro.getAccountInfoSync.mockImplementation(() => {
      throw new Error('account info unavailable')
    })
    vi.stubGlobal('__WOW_BACKEND_API_BASE_URL__', 'https://api.chickenbro.cloud')
    try {
      expect(configuredApiBaseUrl(new MemoryStorage())).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('preserves structured problem codes without accepting a fallback as success', async () => {
    taro.request.mockResolvedValue({
      statusCode: 409,
      data: { error: { code: 'IDEMPOTENCY_CONFLICT' } },
    })
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })

    const result = await transport.request('/api/v2/simc/jobs', {
      method: 'POST',
      auth: { kind: 'mini', accessToken: 'mini-token' },
      responseMode: 'structured-problem',
      fallback: () => ({ id: '' }),
    })

    expect(result).toMatchObject({
      fromFallback: true,
      httpStatus: 409,
      offline: false,
      problemCode: 'IDEMPOTENCY_CONFLICT',
    })
  })

  it('decodes UTF-8 SSE frames across arbitrary chunks and rejects malformed payloads', () => {
    const decoder = new SseDecoder()

    expect(decoder.push(encoded('data: {"type":"delta","text":"你'))).toEqual([])
    expect(decoder.push(encoded('好"}\n\ndata: {"type":"completed"}\n\n'))).toEqual([
      { type: 'delta', text: '你好' },
      { type: 'completed' },
    ])
    expect(decoder.finish()).toEqual([])
    expect(() => new SseDecoder().push(encoded('data: {not-json}\n\n'))).toThrow(
      'malformed SSE payload',
    )
  })

  it('derives Mini auth for chunked SSE and emits complete events', async () => {
    let receive: ((value: { data: ArrayBuffer }) => void) | undefined
    const abort = vi.fn()
    const requestTask = Object.assign(Promise.resolve({ statusCode: 200 }), {
      abort,
      onChunkReceived: vi.fn((listener: (value: { data: ArrayBuffer }) => void) => {
        receive = listener
      }),
    })
    taro.request.mockReturnValue(requestTask)
    const events: unknown[] = []
    const failures: string[] = []
    const onEnd = vi.fn()
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })

    transport.requestSse?.('/api/v2/chat/conversations/id/messages/stream', {
      method: 'POST',
      auth: { kind: 'mini', accessToken: 'mini-token' },
      data: { content: 'hello' },
      header: { 'Idempotency-Key': 'stream-one' },
      onEvent: (event) => events.push(event),
      onFailure: (error) => failures.push(error),
      onEnd,
    })
    receive?.({ data: encoded('data: {"type":"started","sequence":1}\n\n') })
    await requestTask
    await Promise.resolve()

    const request = taro.request.mock.calls[0]?.[0] as {
      credentials?: string
      enableChunked?: boolean
      header?: Record<string, string>
    }
    expect(request.credentials).toBe('omit')
    expect(request.enableChunked).toBe(true)
    expect(request.header).toEqual({
      Accept: 'text/event-stream',
      'Idempotency-Key': 'stream-one',
      Authorization: 'Bearer mini-token',
    })
    expect(events).toEqual([{ type: 'started', sequence: 1 }])
    expect(failures).toEqual([])
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('uses same-origin Web Cookie and CSRF credentials for browser SSE', async () => {
    taro.getEnv.mockReturnValue('WEB')
    vi.stubGlobal('window', { location: { origin: 'https://www.chickenbro.cloud' } })
    vi.stubGlobal('document', {})
    const reader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('data: {"type":"completed"}\n\n'),
        })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    })
    vi.stubGlobal('fetch', fetchMock)
    const events: unknown[] = []
    const failures: string[] = []
    const onEnd = vi.fn()
    try {
      const transport = createTaroTransport({
        storage: new MemoryStorage(),
        resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
      })
      transport.requestSse?.('/api/v2/chat/conversations/id/messages/stream', {
        method: 'POST',
        auth: { kind: 'web', csrfToken: 'web-csrf' },
        data: { content: 'hello' },
        onEvent: (event) => events.push(event),
        onFailure: (error) => failures.push(error),
        onEnd,
      })
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(fetchMock).toHaveBeenCalledWith(
        'https://www.chickenbro.cloud/api/v2/chat/conversations/id/messages/stream',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
          headers: expect.objectContaining({
            Accept: 'text/event-stream',
            'Content-Type': 'application/json',
            'X-CSRF-Token': 'web-csrf',
          }),
          body: JSON.stringify({ content: 'hello' }),
        }),
      )
      expect(events).toEqual([{ type: 'completed' }])
      expect(failures).toEqual([])
      expect(onEnd).toHaveBeenCalledTimes(1)
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('does not report a natural end after the caller aborts a Mini stream', async () => {
    let resolveRequest: ((value: { statusCode: number }) => void) | undefined
    const requestPromise = new Promise<{ statusCode: number }>((resolve) => {
      resolveRequest = resolve
    })
    const abort = vi.fn()
    const requestTask = Object.assign(requestPromise, {
      abort,
      onChunkReceived: vi.fn(),
    })
    taro.request.mockReturnValue(requestTask)
    const failures: string[] = []
    const onEnd = vi.fn()
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })

    const stream = transport.requestSse?.('/api/v2/chat/conversations/id/messages/stream', {
      method: 'POST',
      auth: { kind: 'mini', accessToken: 'mini-token' },
      data: { content: 'hello' },
      onEvent: () => {},
      onFailure: (error) => failures.push(error),
      onEnd,
    })
    stream?.abort()
    resolveRequest?.({ statusCode: 200 })
    await requestPromise
    await Promise.resolve()

    expect(abort).toHaveBeenCalledTimes(1)
    expect(failures).toEqual([])
    expect(onEnd).not.toHaveBeenCalled()
  })

  it('aborts and fails once when a Mini stream consumer rejects an event', async () => {
    let receive: ((value: { data: ArrayBuffer }) => void) | undefined
    const abort = vi.fn()
    const requestTask = Object.assign(Promise.resolve({ statusCode: 200 }), {
      abort,
      onChunkReceived: vi.fn((listener: (value: { data: ArrayBuffer }) => void) => {
        receive = listener
      }),
    })
    taro.request.mockReturnValue(requestTask)
    const failures: string[] = []
    const onEnd = vi.fn()
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveBaseUrl: () => 'https://api.chickenbro.cloud',
    })

    transport.requestSse?.('/api/v2/chat/conversations/id/messages/stream', {
      method: 'POST',
      auth: { kind: 'mini', accessToken: 'mini-token' },
      data: { content: 'hello' },
      onEvent: () => {
        throw new Error('consumer rejected event')
      },
      onFailure: (error) => failures.push(error),
      onEnd,
    })
    receive?.({ data: encoded('data: {"type":"started","sequence":1}\n\n') })
    await requestTask
    await Promise.resolve()

    expect(abort).toHaveBeenCalledTimes(1)
    expect(failures).toEqual(['invalid stream event'])
    expect(onEnd).not.toHaveBeenCalled()
  })
})
