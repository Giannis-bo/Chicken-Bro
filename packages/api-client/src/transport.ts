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

export interface StreamRequestOptions<T> {
  data: RequestData
  header?: Readonly<Record<string, string>>
  timeoutMs?: number
  auth?: boolean
  allowInsecureGuestRequest?: boolean
  attachAnalyticsHeaders?: boolean
  onEvent: (event: T) => void
  onFailure: (error: string) => void
}

export interface ApiStreamTask {
  abort(): void
}

export interface ApiTransport {
  request<T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>>
  requestEndpoint<T>(
    endpointId: EndpointId,
    path: string,
    options: Omit<RequestOptions<T>, 'method'>,
  ): Promise<ApiResult<T>>
  requestStreamEndpoint?<T>(
    endpointId: EndpointId,
    path: string,
    options: Omit<StreamRequestOptions<T>, 'method'>,
  ): ApiStreamTask
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

export class NdjsonDecoder {
  private readonly decoder = new TextDecoder('utf-8')
  private buffered = ''

  push(data: ArrayBuffer): unknown[] {
    this.buffered += this.decoder.decode(new Uint8Array(data), { stream: true })
    return this.takeCompleteLines()
  }

  finish(): unknown[] {
    this.buffered += this.decoder.decode()
    const events = this.takeCompleteLines()
    if (this.buffered.trim()) throw new Error('incomplete NDJSON payload')
    return events
  }

  private takeCompleteLines(): unknown[] {
    const lines = this.buffered.split('\n')
    this.buffered = lines.pop() ?? ''
    const events: unknown[] = []
    for (const line of lines) {
      const text = line.endsWith('\r') ? line.slice(0, -1) : line
      if (!text) continue
      try {
        events.push(JSON.parse(text))
      } catch {
        throw new Error('malformed stream payload')
      }
    }
    return events
  }
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

  const requestStreamEndpoint = <T>(
    endpointId: EndpointId,
    path: string,
    options: Omit<StreamRequestOptions<T>, 'method'>,
  ): ApiStreamTask => {
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
    const baseUrl = resolveBaseUrl()
    const url = baseUrl ? `${baseUrl}${path}` : ''
    let failed = false
    const fail = (message: string) => {
      if (failed) return
      failed = true
      options.onFailure(message)
    }
    if (!url) {
      fail('missing api base url')
      return { abort() {} }
    }
    if (auth && isInsecureHttpUrl(url) && !allowInsecureGuestRequest) {
      fail('insecure api base url for authenticated request')
      return { abort() {} }
    }
    const header: Record<string, string> = {
      ...((options.attachAnalyticsHeaders ?? !(
        'transport' in endpoint && endpoint.transport === 'direct_request_without_analytics_headers'
      )) ? analytics.headers(platform) : {}),
      ...options.header,
    }
    if (auth && !isInsecureHttpUrl(url)) {
      const token = storage.get<string>(storageKey('auth.token'))
      if (token) header['Authorization'] = `Bearer ${token}`
    }

    const decoder = new NdjsonDecoder()
    const task = Taro.request<unknown>({
      url,
      method: endpoint.method,
      data: options.data,
      header,
      timeout: timeoutMs ?? 6000,
      enableChunked: true,
      responseType: 'arraybuffer',
    }) as unknown as Promise<{ statusCode: number }> & {
      abort?: () => void
      onChunkReceived?: (callback: (payload: { data: ArrayBuffer }) => void) => void
    }
    const abort = () => task.abort?.()
    const emit = (event: unknown) => {
      if (failed) return
      try {
        options.onEvent(event as T)
      } catch {
        abort()
        fail('invalid stream event')
      }
    }
    if (typeof task.onChunkReceived !== 'function') {
      abort()
      fail('chunked response is unavailable')
    } else {
      task.onChunkReceived(({ data }) => {
        if (failed) return
        try {
          decoder.push(data).forEach(emit)
        } catch {
          abort()
          fail('malformed stream payload')
        }
      })
    }
    void task.then((response) => {
      if (failed) return
      if (response.statusCode < 200 || response.statusCode >= 300) {
        fail(`HTTP ${response.statusCode}`)
        return
      }
      try {
        decoder.finish().forEach(emit)
      } catch {
        abort()
        fail('malformed stream payload')
      }
    }).catch((error) => fail(errorMessage(error)))
    return { abort }
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
    requestStreamEndpoint,
  }
}
