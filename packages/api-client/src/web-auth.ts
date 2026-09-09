import {
  isQqLoginCreated,
  isLogoutResponse,
  isMeResponse,
  isWebLoginExchangeResponse,
  type QqLoginCreated,
  type MeResponse,
  type LogoutResponse,
  type WebLoginExchangeResponse,
} from '@wow-mini/domain'

import type { ApiResult, ApiTransport } from './transport'
import type { ClientAuthContext } from './auth-context'
import type { TransportAuthContext } from './transport'
import { apiV2Path } from './api-v2-prefix'

declare const __WOW_WEB_CSRF_COOKIE_NAME__: string

export interface WebAuthClient {
  createQqLogin(): Promise<ApiResult<QqLoginCreated>>
  loginTestWeb(account: 'A' | 'B', credential: string): Promise<ApiResult<WebLoginExchangeResponse>>
  me(auth?: Extract<ClientAuthContext, { kind: 'web' }>): Promise<ApiResult<MeResponse>>
  logout(auth?: Extract<ClientAuthContext, { kind: 'web' }>): Promise<ApiResult<LogoutResponse>>
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
    createQqLogin() {
      return webRequest(transport, apiV2Path('/auth/qq/login'), {
        method: 'POST', data: {}, credentials: 'include', auth: { kind: 'public' },
        fallback: () => ({ authorizationUrl: '' }), validate: isQqLoginCreated,
      })
    },
    loginTestWeb(account, credential) {
      return webRequest(transport, apiV2Path('/auth/test/web'), {
        method: 'POST', data: { account, credential }, credentials: 'include',
        auth: { kind: 'public' },
        fallback: () => ({ authenticated: true }), validate: isWebLoginExchangeResponse,
      })
    },
    me(auth) {
      return webRequest(transport, apiV2Path('/me'), {
        credentials: 'include',
        auth: auth ?? { kind: 'public' },
        baseUrl: 'web-auth',
        fallback: () => ({ connected: true, displayName: '' }),
        validate: isMeResponse,
      })
    },
    logout(auth = { kind: 'web', csrfToken: readWebCsrfCookie() }) {
      return webRequest(transport, apiV2Path('/auth/logout'), {
        method: 'POST',
        credentials: 'include',
        auth,
        baseUrl: 'web-auth',
        fallback: () => ({ loggedOut: true }),
        validate: isLogoutResponse,
      })
    },
  }
}
