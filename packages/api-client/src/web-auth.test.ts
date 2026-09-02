import { describe, expect, it, vi } from 'vitest'

import { createWebAuthClient, readWebCsrfCookie } from './web-auth'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'
import type { EndpointId } from '@wow-mini/domain'

class RecordingTransport implements ApiTransport {
  readonly calls: Array<{ path: string; options: RequestOptions<unknown> }> = []

  async request<T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>> {
    this.calls.push({ path, options: options as RequestOptions<unknown> })
    return {
      payload: options.fallback(),
      fromFallback: false,
      error: '',
      httpStatus: 200,
    }
  }

  requestEndpoint<T>(
    _endpointId: EndpointId,
    path: string,
    options: Omit<RequestOptions<T>, 'method'>,
  ): Promise<ApiResult<T>> {
    return this.request(path, options)
  }
}

describe('WebAuthClient', () => {
  it('uses same-origin Cookie credentials without legacy Bearer auth', async () => {
    const transport = new RecordingTransport()
    const client = createWebAuthClient(transport)

    await client.me()
    await client.createWebLoginSession('A'.repeat(43), 'request-key')
    await client.statusWebLoginSession('00000000-0000-4000-8000-000000000000', 'A'.repeat(43))
    await client.exchangeWebLoginSession('00000000-0000-4000-8000-000000000000', 'A'.repeat(43))
    await client.cancelWebLoginSession('00000000-0000-4000-8000-000000000000', 'A'.repeat(43))
    vi.stubGlobal('document', { cookie: '__Host-chickenbro-csrf=web-csrf' })
    await client.logout()
    vi.unstubAllGlobals()

    expect(transport.calls).toHaveLength(6)
    for (const call of transport.calls) {
      expect(call.options.auth).toEqual(
        call.path === '/api/v2/auth/logout'
          ? { kind: 'web', csrfToken: 'web-csrf' }
          : { kind: 'public' },
      )
      expect(call.options.credentials).toBe('include')
      expect(call.options.header?.['Authorization']).toBeUndefined()
      expect(call.options.baseUrl).toBe('web-auth')
    }
    expect(transport.calls[1]?.options.header?.['Idempotency-Key']).toBe('request-key')
  })

  it('sends the mini Bearer explicitly and never includes browser Cookie credentials', async () => {
    const transport = new RecordingTransport()
    const client = createWebAuthClient(transport)

    await client.confirmMiniWebLogin('scene-ticket', 'mini-token')

    const call = transport.calls[0]
    expect(call).toBeDefined()
    if (!call) throw new Error('expected a recorded request')
    expect(call.path).toBe('/api/v2/auth/wechat/mini/web-login-confirm')
    expect(call.options.auth).toEqual({ kind: 'mini', accessToken: 'mini-token' })
    expect(call.options.credentials).toBe('omit')
    expect(call.options.header?.['Authorization']).toBeUndefined()
    expect(call.options.baseUrl).toBe('default')
  })

  it('revokes a Mini bearer independently of the Web cookie session', async () => {
    const transport = new RecordingTransport()
    const client = createWebAuthClient(transport)

    await client.logout({ kind: 'mini', accessToken: 'mini-token' })

    expect(transport.calls[0]?.path).toBe('/api/v2/auth/logout')
    expect(transport.calls[0]?.options.auth).toEqual({
      kind: 'mini',
      accessToken: 'mini-token',
    })
    expect(transport.calls[0]?.options.credentials).toBe('omit')
  })

  it('reads only the exact Web CSRF cookie and rejects ambiguity', () => {
    expect(readWebCsrfCookie(
      'other=value; __Host-chickenbro-csrf=web-csrf-token; suffix__Host-chickenbro-csrf=ignored',
    )).toBe('web-csrf-token')
    expect(() => readWebCsrfCookie('other=value')).toThrow('WEB_CSRF_COOKIE_MISSING')
    expect(() => readWebCsrfCookie(
      '__Host-chickenbro-csrf=first; __Host-chickenbro-csrf=second',
    )).toThrow('WEB_CSRF_COOKIE_INVALID')
  })

  it('uses the configured candidate API prefix for the Web auth surface', async () => {
    vi.stubGlobal('__WOW_WEB_AUTH_API_PREFIX__', '/api/v2-candidate')
    try {
      const transport = new RecordingTransport()
      const client = createWebAuthClient(transport)

      await client.me()

      expect(transport.calls[0]?.path).toBe('/api/v2-candidate/me')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('reads only the configured candidate CSRF cookie', () => {
    vi.stubGlobal('__WOW_WEB_CSRF_COOKIE_NAME__', '__Host-chickenbro-candidate-csrf')
    try {
      expect(readWebCsrfCookie(
        '__Host-chickenbro-csrf=production; __Host-chickenbro-candidate-csrf=candidate-token',
      )).toBe('candidate-token')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
