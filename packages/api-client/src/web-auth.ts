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

declare const __WOW_WEB_AUTH_API_PREFIX__: string

const DEFAULT_WEB_AUTH_API_PREFIX = '/api/v2'

function webAuthApiPrefix(): string {
  const configured = typeof __WOW_WEB_AUTH_API_PREFIX__ === 'string'
    ? __WOW_WEB_AUTH_API_PREFIX__.trim()
    : ''
  return /^\/[A-Za-z0-9][A-Za-z0-9/_-]*$/u.test(configured)
    ? configured.replace(/\/+$/u, '')
    : DEFAULT_WEB_AUTH_API_PREFIX
}

function webAuthPath(path: string): string {
  return `${webAuthApiPrefix()}${path}`
}

export interface WebAuthClient {
  createWebLoginSession(browserVerifier: string, idempotencyKey: string): Promise<ApiResult<WebLoginCreated>>
  statusWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginStatusResponse>>
  exchangeWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginExchangeResponse>>
  cancelWebLoginSession(sessionId: string, browserVerifier: string): Promise<ApiResult<WebLoginStatusResponse>>
  exchangeMiniCode(code: string): Promise<ApiResult<MiniExchangeResponse>>
  confirmMiniWebLogin(sceneTicket: string, accessToken: string): Promise<ApiResult<ConfirmResponse>>
  me(): Promise<ApiResult<MeResponse>>
  logout(): Promise<ApiResult<LogoutResponse>>
}

function webRequest<T>(transport: ApiTransport, path: string, options: {
  method?: 'GET' | 'POST'
  data?: Readonly<Record<string, unknown>>
  header?: Readonly<Record<string, string>>
  credentials: 'omit' | 'include'
  fallback: () => T
  validate: (value: unknown) => boolean
}): Promise<ApiResult<T>> {
  return transport.request(path, {
    ...options,
    auth: false,
    baseUrl: 'web-auth',
    responseMode: 'structured-problem',
  })
}

export function createWebAuthClient(transport: ApiTransport): WebAuthClient {
  return {
    createWebLoginSession(browserVerifier, idempotencyKey) {
      return webRequest(transport, webAuthPath('/auth/wechat/web/login-sessions'), {
        method: 'POST',
        data: { browserVerifier },
        header: { 'Idempotency-Key': idempotencyKey },
        credentials: 'include',
        fallback: () => ({ sessionId: '', expiresAt: '', qrDataUrl: '' }),
        validate: isWebLoginCreated,
      })
    },
    statusWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, webAuthPath(`/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}`), {
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        fallback: () => ({ status: 'expired', expiresAt: '' }),
        validate: isWebLoginStatusResponse,
      })
    },
    exchangeWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, webAuthPath(`/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}/exchange`), {
        method: 'POST',
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        fallback: () => ({ authenticated: true }),
        validate: isWebLoginExchangeResponse,
      })
    },
    cancelWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, webAuthPath(`/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}/cancel`), {
        method: 'POST',
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        fallback: () => ({ status: 'cancelled', expiresAt: '' }),
        validate: isWebLoginStatusResponse,
      })
    },
    exchangeMiniCode(code) {
      return webRequest(transport, webAuthPath('/auth/wechat/mini/exchange'), {
        method: 'POST',
        data: { code },
        credentials: 'omit',
        fallback: () => ({ accessToken: '', expiresAt: '' }),
        validate: isMiniExchangeResponse,
      })
    },
    confirmMiniWebLogin(sceneTicket, accessToken) {
      return webRequest(transport, webAuthPath('/auth/wechat/mini/web-login-confirm'), {
        method: 'POST',
        data: { sceneTicket },
        header: { Authorization: `Bearer ${accessToken}` },
        credentials: 'omit',
        fallback: () => ({ confirmed: true }),
        validate: isConfirmResponse,
      })
    },
    me() {
      return webRequest(transport, webAuthPath('/me'), {
        credentials: 'include',
        fallback: () => ({ connected: true, displayName: '' }),
        validate: isMeResponse,
      })
    },
    logout() {
      return webRequest(transport, webAuthPath('/auth/logout'), {
        method: 'POST',
        credentials: 'include',
        fallback: () => ({ loggedOut: true }),
        validate: isLogoutResponse,
      })
    },
  }
}
