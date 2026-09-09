import { describe, expect, it, vi } from 'vitest'

import { createWebAuthClient, readWebCsrfCookie } from './web-auth'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

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

}

describe('WebAuthClient', () => {
  it('starts QQ login with an empty same-origin POST', async () => {
    const transport = new RecordingTransport()
    await createWebAuthClient(transport).createQqLogin()
    expect(transport.calls[0]).toMatchObject({ path: '/api/v2/auth/qq/login', options: {
      method: 'POST', credentials: 'include', auth: { kind: 'public' }, data: {},
    } })
  })
  it('issues retained test Web sessions with cookie credentials and no client owner', async () => {
    const transport = new RecordingTransport()
    const client = createWebAuthClient(transport)
    await client.loginTestWeb('B', 'other-test-credential')
    expect(transport.calls[0]?.path).toBe('/api/v2/auth/test/web')
    expect(transport.calls[0]?.options).toMatchObject({
      credentials: 'include', baseUrl: 'web-auth', auth: { kind: 'public' },
      data: { account: 'B', credential: 'other-test-credential' },
    })
  })
  it('uses same-origin Cookie credentials without legacy Bearer auth', async () => {
    const transport = new RecordingTransport()
    const client = createWebAuthClient(transport)

    await client.me()
    await client.createQqLogin()
    vi.stubGlobal('document', { cookie: '__Host-chickenbro-csrf=web-csrf' })
    await client.logout()
    vi.unstubAllGlobals()

    expect(transport.calls).toHaveLength(3)
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
