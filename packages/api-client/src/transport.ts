import Taro from '@tarojs/taro'

import {
  endpointContract,
  storageKey,
  type EndpointId,
} from '@wow-mini/domain'

import { AnalyticsIdentity } from './analytics'
import { taroStorage, type StorageAdapter } from './storage'

declare const __WOW_BACKEND_API_BASE_URL__: string

export const DEV_API_BASE_URL = 'http://124.223.51.33'

export interface ApiResult<T> {
  payload: T
  fromFallback: boolean
  error: string
  httpStatus?: number
  transportError?: string
  offline?: boolean
}

export type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'
export type RequestData = Readonly<Record<string, unknown>> | string | ArrayBuffer

export interface RequestOptions<T> {
  method?: RequestMethod
  data?: RequestData
  header?: Readonly<Record<string, string>>
  timeoutMs?: number
  auth?: boolean
  allowInsecureGuestRequest?: boolean
  attachAnalyticsHeaders?: boolean
  responseMode?: 'default' | 'structured-problem'
  fallback: () => T
  validate?: (value: unknown) => boolean
}

export interface ApiTransport {
  request<T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>>
  requestEndpoint<T>(
    endpointId: EndpointId,
    path: string,
    options: Omit<RequestOptions<T>, 'method'>,
  ): Promise<ApiResult<T>>
}

export interface TransportConfig {
  storage?: StorageAdapter
  platform?: string
  resolveBaseUrl?: () => string
}

export function isInsecureHttpUrl(url: string): boolean {
  return /^http:\/\//i.test(url)
}

function isWebRuntime(): boolean {
  try {
    const environment = Taro.getEnv()
    if (environment) return environment === Taro.ENV_TYPE.WEB
  } catch {
    // Unit tests and non-Taro callers may not provide the runtime environment API.
  }
  return typeof window !== 'undefined' && typeof document !== 'undefined'
}

type MiniProgramEnvVersion = 'develop' | 'trial' | 'release' | 'unknown'

function miniProgramEnvVersion(): MiniProgramEnvVersion {
  if (isWebRuntime()) return 'develop'
  try {
    const value = Taro.getAccountInfoSync().miniProgram?.envVersion
    return value === 'develop' || value === 'trial' || value === 'release'
      ? value
      : 'unknown'
  } catch {
    return 'unknown'
  }
}

function buildTimeApiBaseUrl(): string {
  return typeof __WOW_BACKEND_API_BASE_URL__ === 'string'
    ? __WOW_BACKEND_API_BASE_URL__
    : ''
}

function h5ApiBaseUrl(): string {
  if (!isWebRuntime()) return ''
  return `${window.location.origin}/wow-api`
}

function productionApiBaseUrl(value: string): string {
  try {
    const parsed = new URL(value)
    const isIpv4 = /^(?:\d{1,3}\.){3}\d{1,3}$/.test(parsed.hostname)
    const isIpv6 = parsed.hostname.includes(':')
    const isNamedHost = parsed.hostname.includes('.') && !isIpv4 && !isIpv6
    const isOriginOnly = parsed.pathname === '/' && !parsed.search && !parsed.hash
      && !parsed.username && !parsed.password
    return parsed.protocol === 'https:' && isNamedHost && isOriginOnly
      ? parsed.origin
      : ''
  } catch {
    return ''
  }
}

export function configuredApiBaseUrl(storage: StorageAdapter = taroStorage): string {
  if (isWebRuntime()) {
    const stored = storage.get<string>(storageKey('api.base'))
      ?? storage.get<string>(storageKey('api.newsBaseCompat'))
    return stored || buildTimeApiBaseUrl() || h5ApiBaseUrl()
  }
  const envVersion = miniProgramEnvVersion()
  if (envVersion === 'unknown') return ''
  if (envVersion === 'release' || envVersion === 'trial') {
    return productionApiBaseUrl(buildTimeApiBaseUrl())
  }
  const stored = storage.get<string>(storageKey('api.base'))
    ?? storage.get<string>(storageKey('api.newsBaseCompat'))
  if (stored) return stored
  const envBase = buildTimeApiBaseUrl()
  if (envBase) return envBase
  return DEV_API_BASE_URL
}

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'object' && error !== null && 'errMsg' in error) {
    const value = error.errMsg
    if (typeof value === 'string' && value) return value
  }
  return 'request failed'
}

export function createTaroTransport(config: TransportConfig = {}): ApiTransport {
  const storage = config.storage ?? taroStorage
  const analytics = new AnalyticsIdentity(storage)
  const platform = config.platform ?? (isWebRuntime() ? 'h5' : 'miniprogram')
  const resolveBaseUrl = config.resolveBaseUrl ?? (() => configuredApiBaseUrl(storage))

  const request = async <T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>> => {
    const structuredProblem = options.responseMode === 'structured-problem'
    const fallbackResult = (error: string, httpStatus = 0, offline = false): ApiResult<T> => ({
      payload: options.fallback(),
      fromFallback: true,
      error,
      ...(structuredProblem ? { httpStatus, transportError: error, offline } : {}),
    })
    const baseUrl = resolveBaseUrl()
    const url = baseUrl ? `${baseUrl}${path}` : ''
    if (!url) {
      return fallbackResult('missing api base url', 0, true)
    }
    if (options.auth && isInsecureHttpUrl(url) && !options.allowInsecureGuestRequest) {
      return fallbackResult('insecure api base url for authenticated request')
    }

    const header: Record<string, string> = {
      ...(options.attachAnalyticsHeaders === false ? {} : analytics.headers(platform)),
      ...options.header,
    }
    if (options.auth && !isInsecureHttpUrl(url)) {
      const token = storage.get<string>(storageKey('auth.token'))
      if (token) header['Authorization'] = `Bearer ${token}`
    }

    try {
      const response = await Taro.request<unknown>({
        url,
        method: options.method ?? 'GET',
        data: options.data,
        header,
        timeout: options.timeoutMs ?? 6000,
      })
      const valid = options.validate?.(response.data) ?? Boolean(response.data)
      if (structuredProblem && valid) {
        return {
          payload: response.data as T,
          fromFallback: false,
          error: '',
          httpStatus: response.statusCode,
          transportError: '',
          offline: false,
        }
      }
      if (response.statusCode >= 200 && response.statusCode < 300 && valid) {
        return { payload: response.data as T, fromFallback: false, error: '' }
      }
      return fallbackResult(`HTTP ${response.statusCode}`, response.statusCode)
    } catch (error) {
      return fallbackResult(errorMessage(error), 0, true)
    }
  }

  return {
    request,
    requestEndpoint<T>(
      endpointId: EndpointId,
      path: string,
      options: Omit<RequestOptions<T>, 'method'>,
    ): Promise<ApiResult<T>> {
      const endpoint = endpointContract(endpointId)
      const endpointAllowsInsecureGuest = 'allowInsecureGuestRequest' in endpoint
        && endpoint.allowInsecureGuestRequest === true
      const allowInsecureGuestRequest = endpointAllowsInsecureGuest
        && options.allowInsecureGuestRequest === true
      const auth = endpoint.auth === 'optional_by_call'
        ? options.auth === true
        : endpoint.auth !== 'none'
      const timeoutMs = options.timeoutMs
        ?? ('timeoutMs' in endpoint ? endpoint.timeoutMs : undefined)
      return request(path, {
        ...options,
        method: endpoint.method,
        ...(timeoutMs === undefined ? {} : { timeoutMs }),
        auth,
        allowInsecureGuestRequest,
        attachAnalyticsHeaders: !(
          'transport' in endpoint
          && endpoint.transport === 'direct_request_without_analytics_headers'
        ),
      })
    },
  }
}
