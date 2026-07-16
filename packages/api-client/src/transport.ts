import Taro from '@tarojs/taro'

import {
  endpointContract,
  storageKey,
  type EndpointId,
} from '@wow-mini/domain'

import { AnalyticsIdentity } from './analytics'
import { taroStorage, type StorageAdapter } from './storage'

export const DEV_API_BASE_URL = 'http://124.223.51.33'

export interface ApiResult<T> {
  payload: T
  fromFallback: boolean
  error: string
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

function miniProgramEnvVersion(): string {
  if (isWebRuntime()) return 'develop'
  try {
    return Taro.getAccountInfoSync().miniProgram?.envVersion ?? 'develop'
  } catch {
    return 'develop'
  }
}

function buildTimeApiBaseUrl(): string {
  if (typeof process === 'undefined' || !process.env) return ''
  return process.env['WOW_BACKEND_API_BASE_URL']
    ?? process.env['WOW_NEWS_API_BASE_URL']
    ?? ''
}

function h5ApiBaseUrl(): string {
  if (!isWebRuntime()) return ''
  return `${window.location.origin}/wow-api`
}

export function configuredApiBaseUrl(storage: StorageAdapter = taroStorage): string {
  const stored = storage.get<string>(storageKey('api.base'))
    ?? storage.get<string>(storageKey('api.newsBaseCompat'))
  if (stored) return stored
  const envBase = buildTimeApiBaseUrl()
  if (envBase) return envBase
  const h5Base = h5ApiBaseUrl()
  if (h5Base) return h5Base
  return miniProgramEnvVersion() === 'develop' ? DEV_API_BASE_URL : ''
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
    const baseUrl = resolveBaseUrl()
    const url = baseUrl ? `${baseUrl}${path}` : ''
    if (!url) {
      return { payload: options.fallback(), fromFallback: true, error: 'missing api base url' }
    }
    if (options.auth && isInsecureHttpUrl(url) && !options.allowInsecureGuestRequest) {
      return {
        payload: options.fallback(),
        fromFallback: true,
        error: 'insecure api base url for authenticated request',
      }
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
      if (response.statusCode >= 200 && response.statusCode < 300 && valid) {
        return { payload: response.data as T, fromFallback: false, error: '' }
      }
      return {
        payload: options.fallback(),
        fromFallback: true,
        error: `HTTP ${response.statusCode}`,
      }
    } catch (error) {
      return {
        payload: options.fallback(),
        fromFallback: true,
        error: errorMessage(error),
      }
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
