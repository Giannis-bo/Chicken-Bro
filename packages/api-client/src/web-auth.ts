import {
  isConfirmResponse,
  isLogoutResponse,
  isMeResponse,
  isMiniExchangeResponse,
  isWebLoginCreated,
  isWebLoginExchangeResponse,
  isWebLoginStatusResponse,
  type ConfirmResponse,
  type MeResponse,
  type MiniExchangeResponse,
  type LogoutResponse,
  type WebLoginCreated,
  type WebLoginExchangeResponse,
  type WebLoginStatusResponse,
} from '@wow-mini/domain'

import type { ApiResult, ApiTransport } from './transport'
import type { ClientAuthContext } from './auth-context'
import type { TransportAuthContext } from './transport'
import { apiV2Path } from './api-v2-prefix'

declare const __WOW_WEB_CSRF_COOKIE_NAME__: string

export interface WebAuthClient {
  loginTestMini(account: 'A' | 'B', credential: string): Promise<ApiResult<MiniExchangeResponse>>
  loginTestWeb(account: 'A' | 'B', credential: string): Promise<ApiResult<WebLoginExchangeResponse>>
  createWebLoginSession(browserVerifier: string, idempotencyKey: string): Promise<ApiResult<WebLoginCreated>>
  statusWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginStatusResponse>>
  exchangeWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginExchangeResponse>>
  cancelWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginStatusResponse>>
  exchangeMiniCode(code: string): Promise<ApiResult<MiniExchangeResponse>>
  confirmMiniWebLogin(sceneTicket: string, accessToken: string): Promise<ApiResult<ConfirmResponse>>
  me(auth?: ClientAuthContext): Promise<ApiResult<MeResponse>>
  logout(auth?: ClientAuthContext): Promise<ApiResult<LogoutResponse>>
}

const DEFAULT_WEB_CSRF_COOKIE = '__Host-chickenbro-csrf'

function webCsrfCookieName(): string {
  const configured = typeof __WOW_WEB_CSRF_COOKIE_NAME__ === 'string'
    ? __WOW_WEB_CSRF_COOKIE_NAME__.trim()
    : ''
  return configured.startsWith('__Host-') && !/\s/u.test(configured)
    ? configured
    : DEFAULT_WEB_CSRF_COOKIE
}

export function readWebCsrfCookie(cookieHeader: string = (
  typeof document === 'undefined' ? '' : document.cookie
)): string {
  const cookieName = webCsrfCookieName()
  const matches = cookieHeader
    .split(';')
    .map((part) => part.trim())
    .filter((part) => part.startsWith(`${cookieName}=`))
  if (matches.length === 0) throw new Error('WEB_CSRF_COOKIE_MISSING')
  if (matches.length !== 1) throw new Error('WEB_CSRF_COOKIE_INVALID')
  const encoded = matches[0]?.slice(cookieName.length + 1) ?? ''
  let value = ''
  try {
    value = decodeURIComponent(encoded)
  } catch {
    throw new Error('WEB_CSRF_COOKIE_INVALID')
  }
  if (!value || value.length > 512 || /\s/u.test(value)) {
    throw new Error('WEB_CSRF_COOKIE_INVALID')
  }
  return value
}

function webRequest<T>(transport: ApiTransport, path: string, options: {
  method?: 'GET' | 'POST'
  data?: Readonly<Record<string, unknown>>
  header?: Readonly<Record<string, string>>
  credentials: 'omit' | 'include'
  auth: TransportAuthContext
  baseUrl?: 'default' | 'web-auth'
  fallback: () => T
  validate: (value: unknown) => boolean
}): Promise<ApiResult<T>> {
  return transport.request(path, {
    ...options,
    baseUrl: options.baseUrl ?? 'web-auth',
    responseMode: 'structured-problem',
  })
}

export function createWebAuthClient(transport: ApiTransport): WebAuthClient {
  return {
    loginTestMini(account, credential) {
      return webRequest(transport, apiV2Path('/auth/test/mini'), {
        method: 'POST', data: { account, credential }, credentials: 'omit',
        auth: { kind: 'public' }, baseUrl: 'default',
        fallback: () => ({ accessToken: '', expiresAt: '' }), validate: isMiniExchangeResponse,
      })
    },
    loginTestWeb(account, credential) {
      return webRequest(transport, apiV2Path('/auth/test/web'), {
        method: 'POST', data: { account, credential }, credentials: 'include',
        auth: { kind: 'public' },
        fallback: () => ({ authenticated: true }), validate: isWebLoginExchangeResponse,
      })
    },
    createWebLoginSession(browserVerifier, idempotencyKey) {
      return webRequest(transport, apiV2Path('/auth/wechat/web/login-sessions'), {
        method: 'POST',
        data: { browserVerifier },
        header: { 'Idempotency-Key': idempotencyKey },
        credentials: 'include',
        auth: { kind: 'public' },
        fallback: () => ({ sessionId: '', expiresAt: '', qrDataUrl: '' }),
        validate: isWebLoginCreated,
      })
    },
    statusWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, apiV2Path(`/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}`), {
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        auth: { kind: 'public' },
        fallback: () => ({ status: 'expired', expiresAt: '' }),
        validate: isWebLoginStatusResponse,
      })
    },
    exchangeWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, apiV2Path(`/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}/exchange`), {
        method: 'POST',
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        auth: { kind: 'public' },
        fallback: () => ({ authenticated: true }),
        validate: isWebLoginExchangeResponse,
      })
    },
    cancelWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, apiV2Path(`/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}/cancel`), {
        method: 'POST',
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        auth: { kind: 'public' },
        fallback: () => ({ status: 'cancelled', expiresAt: '' }),
        validate: isWebLoginStatusResponse,
      })
    },
    exchangeMiniCode(code) {
      return webRequest(transport, apiV2Path('/auth/wechat/mini/exchange'), {
        method: 'POST',
        data: { code },
        credentials: 'omit',
        auth: { kind: 'public' },
        baseUrl: 'default',
        fallback: () => ({ accessToken: '', expiresAt: '' }),
        validate: isMiniExchangeResponse,
      })
    },
    confirmMiniWebLogin(sceneTicket, accessToken) {
      return webRequest(transport, apiV2Path('/auth/wechat/mini/web-login-confirm'), {
        method: 'POST',
        data: { sceneTicket },
        credentials: 'omit',
        auth: { kind: 'mini', accessToken },
        baseUrl: 'default',
        fallback: () => ({ confirmed: true }),
        validate: isConfirmResponse,
      })
    },
    me(auth) {
      return webRequest(transport, apiV2Path('/me'), {
        credentials: auth?.kind === 'mini' ? 'omit' : 'include',
        auth: auth ?? { kind: 'public' },
        baseUrl: auth?.kind === 'mini' ? 'default' : 'web-auth',
        fallback: () => ({ connected: true, displayName: '' }),
        validate: isMeResponse,
      })
    },
    logout(auth = { kind: 'web', csrfToken: readWebCsrfCookie() }) {
      const credentials = auth.kind === 'web' ? 'include' : 'omit'
      return webRequest(transport, apiV2Path('/auth/logout'), {
        method: 'POST',
        credentials,
        auth,
        baseUrl: auth.kind === 'web' ? 'web-auth' : 'default',
        fallback: () => ({ loggedOut: true }),
        validate: isLogoutResponse,
      })
    },
  }
}
