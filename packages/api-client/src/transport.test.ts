import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  configuredApiBaseUrl,
  createTaroTransport,
  DEV_API_BASE_URL,
  SseDecoder,
} from './transport'
import type { RequestOptions } from './transport'
import type { StorageAdapter } from './storage'
import { createWebAuthClient } from './web-auth'

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

  it.each(['/api/v2', '/api/v2-candidate', '/test/api/v2'])(
    'sends test login and session recovery through the real transport at %s', async (prefix) => {
      vi.stubGlobal('__WOW_API_V2_PREFIX__', prefix)
      vi.stubGlobal('__WOW_TEST_LOGIN__', true)
      try {
        const client = createWebAuthClient(createTaroTransport({
          resolveBaseUrl: () => 'https://api.chickenbro.cloud',
          resolveWebBaseUrl: () => 'https://www.chickenbro.cloud',
        }))
        taro.request.mockResolvedValueOnce({ statusCode: 200, data: { authenticated: true } })
        taro.request.mockResolvedValueOnce({ statusCode: 200, data: { connected: true, displayName: '测试账号 A' } })
        const web = await client.loginTestWeb('A', 'a'.repeat(32))
        const me = await client.me()
        expect([web.error, me.error]).toEqual(['', ''])
        expect(taro.request.mock.calls.map(([request]) => ({
          url: request.url, credentials: request.credentials, header: request.header,
        }))).toEqual([
          { url: `https://www.chickenbro.cloud${prefix}/auth/test/web`, credentials: 'include', header: {} },
          { url: `https://www.chickenbro.cloud${prefix}/me`, credentials: 'include', header: {} },
        ])
      } finally { vi.unstubAllGlobals() }
    },
  )

  it('keeps test login disabled in formal builds', async () => {
    const client = createWebAuthClient(createTaroTransport({ resolveBaseUrl: () => 'https://api.chickenbro.cloud' }))
    expect((await client.loginTestWeb('A', 'a'.repeat(32))).fromFallback).toBe(true)
    expect(taro.request).not.toHaveBeenCalled()
  })

  it.each(['/test/api/v2/chat/conversations', '/test/api/v2/simc/jobs', '/test/api/v2/auth/test/web/extra', '/other/api/v2/me', '/api/v2/me'])(
    'rejects public business routes and mismatched configured prefixes: %s', async (path) => {
      vi.stubGlobal('__WOW_API_V2_PREFIX__', '/test/api/v2')
      vi.stubGlobal('__WOW_TEST_LOGIN__', true)
      try {
        const transport = createTaroTransport({ resolveBaseUrl: () => 'https://api.chickenbro.cloud' })
        expect((await transport.request(path, { auth: { kind: 'public' }, fallback: () => ({}) })).fromFallback).toBe(true)
        expect(taro.request).not.toHaveBeenCalled()
      } finally { vi.unstubAllGlobals() }
    },
  )

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
      resolveWebBaseUrl: () => 'http://example.test',
    })

    const result = await transport.request('/api/v2/simc/jobs', {
      auth: { kind: 'web', csrfToken: 'web-csrf' },
      fallback: () => ({ items: [] }),
    })

    expect(result.fromFallback).toBe(true)
    expect(result.error).toContain('insecure')
    expect(taro.request).not.toHaveBeenCalled()
  })

  it.each(['ftp://example.test', 'not-a-url'])('rejects every non-HTTPS authenticated origin: %s', async (origin) => {
    const transport = createTaroTransport({
      storage: new MemoryStorage(),
      resolveWebBaseUrl: () => origin,
    })

    const result = await transport.request('/api/v2/simc/jobs', {
      auth: { kind: 'web', csrfToken: 'web-csrf' },
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
      auth: { kind: 'web', csrfToken: 'web-csrf' },
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
    const login = await transport.request('/api/v2/auth/qq/login', {
      method: 'POST',
      auth: { kind: 'public' },
      baseUrl: 'web-auth',
      credentials: 'include',
      fallback: () => ({ authorizationUrl: '' }),
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
      auth: { kind: 'web', csrfToken: 'web-csrf' },
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


  it.each(['abort', 'consumer', 'timeout'] as const)('browser SSE %s never reports normal completion', async mode => {
    taro.getEnv.mockReturnValue('WEB')
    const onEnd = vi.fn(), onFailure = vi.fn()
    let resolveRead!: (value: { done: boolean; value?: Uint8Array }) => void
    let signal!: AbortSignal
    const reader = { read: vi.fn(() => new Promise<{done: boolean; value?: Uint8Array}>(resolve => { resolveRead = resolve })) }
    vi.stubGlobal('fetch', vi.fn((_url: string, options: RequestInit) => {
      signal = options.signal as AbortSignal
      return Promise.resolve({ ok: true, body: { getReader: () => reader } })
    }))
    try {
      const task = createTaroTransport({ resolveWebBaseUrl: () => 'https://www.chickenbro.cloud' }).requestSse?.('/api/v2/chat/conversations/id/messages/stream', {
        auth: { kind: 'web', csrfToken: 'csrf' }, timeoutMs: mode === 'timeout' ? 5 : 1000,
        onEvent: () => { if (mode === 'consumer') throw new Error('invalid event') }, onFailure, onEnd,
      })
      await Promise.resolve()
      if (mode === 'abort') task?.abort()
      if (mode === 'consumer') {
        resolveRead({ done: false, value: new TextEncoder().encode('data: {"type":"delta","text":"x"}\n\n') })
        await Promise.resolve()
      }
      if (mode === 'timeout') await new Promise(resolve => setTimeout(resolve, 15))
      resolveRead({ done: true })
      await new Promise(resolve => setTimeout(resolve, 0))
      expect(signal.aborted).toBe(true)
      expect(onEnd).not.toHaveBeenCalled()
      expect(onFailure).toHaveBeenCalledTimes(mode === 'abort' ? 0 : 1)
    } finally { vi.unstubAllGlobals() }
  })

})
