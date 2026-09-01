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
      return webRequest(transport, '/api/v2/auth/wechat/web/login-sessions', {
        method: 'POST',
        data: { browserVerifier },
        header: { 'Idempotency-Key': idempotencyKey },
        credentials: 'include',
        fallback: () => ({ sessionId: '', expiresAt: '', qrDataUrl: '' }),
        validate: isWebLoginCreated,
      })
    },
    statusWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, `/api/v2/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}`, {
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        fallback: () => ({ status: 'expired', expiresAt: '' }),
        validate: isWebLoginStatusResponse,
      })
    },
    exchangeWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, `/api/v2/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}/exchange`, {
        method: 'POST',
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        fallback: () => ({ authenticated: true }),
        validate: isWebLoginExchangeResponse,
      })
    },
    cancelWebLoginSession(sessionId, browserVerifier) {
      return webRequest(transport, `/api/v2/auth/wechat/web/login-sessions/${encodeURIComponent(sessionId)}/cancel`, {
        method: 'POST',
        header: { 'X-Web-Login-Verifier': browserVerifier },
        credentials: 'include',
        fallback: () => ({ status: 'cancelled', expiresAt: '' }),
        validate: isWebLoginStatusResponse,
      })
    },
    exchangeMiniCode(code) {
      return webRequest(transport, '/api/v2/auth/wechat/mini/exchange', {
        method: 'POST',
        data: { code },
        credentials: 'omit',
        fallback: () => ({ accessToken: '', expiresAt: '' }),
        validate: isMiniExchangeResponse,
      })
    },
    confirmMiniWebLogin(sceneTicket, accessToken) {
      return webRequest(transport, '/api/v2/auth/wechat/mini/web-login-confirm', {
        method: 'POST',
        data: { sceneTicket },
        header: { Authorization: `Bearer ${accessToken}` },
        credentials: 'omit',
        fallback: () => ({ confirmed: true }),
        validate: isConfirmResponse,
      })
    },
    me() {
      return webRequest(transport, '/api/v2/me', {
        credentials: 'include',
        fallback: () => ({ connected: true, displayName: '' }),
        validate: isMeResponse,
      })
    },
    logout() {
      return webRequest(transport, '/api/v2/auth/logout', {
        method: 'POST',
        credentials: 'include',
        fallback: () => ({ loggedOut: true }),
        validate: isLogoutResponse,
      })
    },
  }
}
