import Taro from '@tarojs/taro'

import { clientAuthRequest, type ClientAuthContext } from './auth-context'
import { taroStorage, type StorageAdapter } from './storage'
import { apiV2Prefix } from './api-v2-prefix'

declare const __WOW_BACKEND_API_BASE_URL__: string
declare const __WOW_TEST_LOGIN__: boolean

const API_BASE_STORAGE_KEY = 'wow_backend_api_base_url'

export const DEV_API_BASE_URL = 'https://api.chickenbro.cloud'

export interface ApiResult<T> {
  payload: T
  fromFallback: boolean
  error: string
  httpStatus?: number
  transportError?: string
  offline?: boolean
  problemCode?: string
}

export type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'
export type RequestData = Readonly<Record<string, unknown>> | string | ArrayBuffer
export type RequestCredentials = 'omit' | 'same-origin' | 'include'
export type RequestBase = 'default' | 'web-auth'
export type TransportAuthContext = ClientAuthContext | { kind: 'public' }

export interface RequestOptions<T> {
  method?: RequestMethod
  data?: RequestData
  header?: Readonly<Record<string, string>>
  timeoutMs?: number
  auth: TransportAuthContext
  responseMode?: 'default' | 'structured-problem'
  credentials?: RequestCredentials
  baseUrl?: RequestBase
  fallback: () => T
  validate?: (value: unknown) => boolean
}

export interface ApiStreamTask {
  abort(): void
}

export interface SseStreamRequestOptions<T> {
  method?: RequestMethod
  data?: RequestData
  header?: Readonly<Record<string, string>>
  timeoutMs?: number
  auth: ClientAuthContext
  onEvent: (event: T) => void
  onFailure: (error: string) => void
  onEnd?: () => void
}

export interface ApiTransport {
  request<T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>>
  requestSse?<T>(path: string, options: SseStreamRequestOptions<T>): ApiStreamTask
}

export interface TransportConfig {
  storage?: StorageAdapter
  resolveBaseUrl?: () => string
  resolveWebBaseUrl?: () => string
}

function publicAuthPath(path: string): boolean {
  const pathname = path.split(/[?#]/u, 1)[0] ?? ''
  const prefix = apiV2Prefix()
  if (!pathname.startsWith(`${prefix}/`)) return false
  const route = pathname.slice(prefix.length)
  return route === '/health/readiness'
    || route === '/me'
    || route === '/auth/qq/login'
    || (typeof __WOW_TEST_LOGIN__ === 'boolean' && __WOW_TEST_LOGIN__
      && route === '/auth/test/web')
}

function hasExplicitCredentialHeader(header: Readonly<Record<string, string>> | undefined): boolean {
  return Object.keys(header ?? {}).some((key) => {
    const normalized = key.toLowerCase()
    return normalized === 'authorization' || normalized === 'x-csrf-token'
  })
}

export function isInsecureHttpUrl(url: string): boolean {
  try {
    return new URL(url).protocol !== 'https:'
  } catch {
    return true
  }
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
  return window.location.origin
}

function productionApiBaseUrl(value: string): string {
  try {
    const parsed = new URL(value)
    const isIpv4 = /^(?:\d{1,3}\.){3}\d{1,3}$/u.test(parsed.hostname)
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
    return storage.get<string>(API_BASE_STORAGE_KEY) || buildTimeApiBaseUrl() || h5ApiBaseUrl()
  }
  const envVersion = miniProgramEnvVersion()
  if (envVersion === 'unknown') return ''
  if (envVersion === 'release' || envVersion === 'trial') {
    return productionApiBaseUrl(buildTimeApiBaseUrl())
  }
  return storage.get<string>(API_BASE_STORAGE_KEY) || buildTimeApiBaseUrl() || DEV_API_BASE_URL
}

export function configuredWebAuthBaseUrl(storage: StorageAdapter = taroStorage): string {
  if (isWebRuntime()) return window.location.origin
  return productionApiBaseUrl(buildTimeApiBaseUrl()) || configuredApiBaseUrl(storage)
}

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'object' && error !== null && 'errMsg' in error) {
    const value = error.errMsg
    if (typeof value === 'string' && value) return value
  }
  return 'request failed'
}

function responseProblemCode(value: unknown): string | undefined {
  if (
    typeof value === 'object'
    && value !== null
    && 'error' in value
    && typeof value.error === 'object'
    && value.error !== null
    && 'code' in value.error
    && typeof value.error.code === 'string'
  ) {
    return value.error.code
  }
  return undefined
}

// Mini runtimes may lack the browser Encoding API. Keep incomplete UTF-8
// bytes between chunks; decoding each network chunk independently corrupts text.
class Utf8StreamDecoder {
  private pending = new Uint8Array(0)

  decode(input = new Uint8Array(0), options: { stream?: boolean } = {}): string {
    const bytes = new Uint8Array(this.pending.length + input.length)
    bytes.set(this.pending)
    bytes.set(input, this.pending.length)
    let end = bytes.length
    if (options.stream && end) {
      let start = end - 1
      while (start > 0 && (bytes[start]! & 0xc0) === 0x80) start -= 1
      const lead = bytes[start]!
      const length = lead >= 0xf0 && lead <= 0xf4 ? 4
        : lead >= 0xe0 && lead <= 0xef ? 3
          : lead >= 0xc2 && lead <= 0xdf ? 2 : 1
      if (end - start < length) end = start
    }
    this.pending = bytes.slice(end)
    let encoded = ''
    for (let index = 0; index < end; index += 1) {
      encoded += '%' + bytes[index]!.toString(16).padStart(2, '0')
    }
    return decodeURIComponent(encoded)
  }
}

function utf8Decoder() {
  return typeof TextDecoder === 'function' ? new TextDecoder('utf-8') : new Utf8StreamDecoder()
}

export class SseDecoder {
  private readonly decoder = utf8Decoder()
  private buffered = ''

  push(data: ArrayBuffer): unknown[] {
    this.buffered += this.decoder.decode(new Uint8Array(data), { stream: true })
    return this.takeCompleteFrames()
  }

  finish(): unknown[] {
    this.buffered += this.decoder.decode()
    const events = this.takeCompleteFrames()
    if (this.buffered.trim()) {
      events.push(this.parseFrame(this.buffered))
      this.buffered = ''
    }
    return events
  }

  private takeCompleteFrames(): unknown[] {
    const events: unknown[] = []
    const frames = this.buffered.split(/\r?\n\r?\n/u)
    this.buffered = frames.pop() ?? ''
    for (const frame of frames) {
      if (frame.trim()) events.push(this.parseFrame(frame))
    }
    return events
  }

  private parseFrame(frame: string): unknown {
    const data = frame.split(/\r?\n/u)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /u, ''))
      .join('\n')
    if (!data) throw new Error('malformed SSE payload')
    try {
      return JSON.parse(data)
    } catch {
      throw new Error('malformed SSE payload')
    }
  }
}

export function createTaroTransport(config: TransportConfig = {}): ApiTransport {
  const storage = config.storage ?? taroStorage
  const resolveBaseUrl = config.resolveBaseUrl ?? (() => configuredApiBaseUrl(storage))
  const resolveWebBaseUrl = config.resolveWebBaseUrl ?? (() => configuredWebAuthBaseUrl(storage))

  const request = async <T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>> => {
    const structuredProblem = options.responseMode === 'structured-problem'
    const fallbackResult = (
      error: string,
      httpStatus = 0,
      offline = false,
      problemCode?: string,
    ): ApiResult<T> => ({
      payload: options.fallback(),
      fromFallback: true,
      error,
      ...(structuredProblem
        ? { httpStatus, transportError: error, offline, ...(problemCode ? { problemCode } : {}) }
        : {}),
    })

    let effectiveBase = options.baseUrl ?? 'default'
    let effectiveCredentials = options.credentials ?? 'omit'
    let credentialHeader: Readonly<Record<string, string>> = {}
    let requiresSecureTransport = false
    if (options.auth === undefined) {
      return fallbackResult('auth context is required')
    }
    if (hasExplicitCredentialHeader(options.header)) {
      return fallbackResult('auth context cannot be combined with explicit credential headers')
    }
    if (options.auth.kind === 'public') {
      if (!publicAuthPath(path)) {
        return fallbackResult('public auth context is not allowed for this path')
      }
      requiresSecureTransport = !/\/health\/readiness(?:[?#]|$)/u.test(path)
    } else {
      try {
        const derived = clientAuthRequest(options.auth, {
          mutating: (options.method ?? 'GET') !== 'GET',
        })
        if (options.baseUrl !== undefined && options.baseUrl !== derived.baseUrl) {
          return fallbackResult('auth context conflicts with request base')
        }
        if (options.credentials !== undefined && options.credentials !== derived.credentials) {
          return fallbackResult('auth context conflicts with request credentials')
        }
        effectiveBase = derived.baseUrl
        effectiveCredentials = derived.credentials
        credentialHeader = derived.header
        requiresSecureTransport = true
      } catch (error) {
        return fallbackResult(errorMessage(error))
      }
    }

    const baseUrl = (effectiveBase === 'web-auth' ? resolveWebBaseUrl : resolveBaseUrl)()
    const url = baseUrl ? `${baseUrl}${path}` : ''
    if (!url) return fallbackResult('missing api base url', 0, true)
    if (requiresSecureTransport && isInsecureHttpUrl(url)) {
      return fallbackResult('insecure api base url for authenticated request')
    }

    try {
      const response = await Taro.request<unknown>({
        url,
        method: options.method ?? 'GET',
        data: options.data,
        header: { ...options.header, ...credentialHeader },
        timeout: options.timeoutMs ?? 6000,
        credentials: effectiveCredentials,
      })
      const valid = options.validate?.(response.data) ?? Boolean(response.data)
      if (response.statusCode >= 200 && response.statusCode < 300 && valid) {
        return {
          payload: response.data as T,
          fromFallback: false,
          error: '',
          ...(structuredProblem
            ? { httpStatus: response.statusCode, transportError: '', offline: false }
            : {}),
        }
      }
      return fallbackResult(
        `HTTP ${response.statusCode}`,
        response.statusCode,
        false,
        responseProblemCode(response.data),
      )
    } catch (error) {
      return fallbackResult(errorMessage(error), 0, true)
    }
  }

  const requestSse = <T>(
    path: string,
    options: SseStreamRequestOptions<T>,
  ): ApiStreamTask => {
    let failed = false
    let aborted = false
    let ended = false
    const fail = (message: string) => {
      if (failed || aborted || ended) return
      failed = true
      options.onFailure(message)
    }
    const end = () => {
      if (failed || aborted || ended) return
      ended = true
      options.onEnd?.()
    }
    if (hasExplicitCredentialHeader(options.header)) {
      fail('auth context cannot be combined with explicit credential headers')
      return { abort() {} }
    }

    let authRequest
    try {
      authRequest = clientAuthRequest(options.auth, {
        mutating: (options.method ?? 'POST') !== 'GET',
      })
    } catch (error) {
      fail(errorMessage(error))
      return { abort() {} }
    }
    const baseUrl = (authRequest.baseUrl === 'web-auth' ? resolveWebBaseUrl : resolveBaseUrl)()
    const url = baseUrl ? `${baseUrl}${path}` : ''
    if (!url) {
      fail('missing api base url')
      return { abort() {} }
    }
    if (isInsecureHttpUrl(url)) {
      fail('insecure api base url for authenticated request')
      return { abort() {} }
    }

    const decoder = new SseDecoder()
    const header: Record<string, string> = {
      Accept: 'text/event-stream',
      ...options.header,
      ...authRequest.header,
    }
    const emit = (event: unknown, abort: () => void) => {
      if (failed || aborted || ended) return
      try {
        options.onEvent(event as T)
      } catch {
        fail('invalid stream event')
        abort()
      }
    }

    if (isWebRuntime() && typeof fetch === 'function') {
      const controller = new AbortController()
      let timeoutHandle: ReturnType<typeof setTimeout> | undefined
      const clearRequestTimeout = () => {
        if (timeoutHandle !== undefined) {
          clearTimeout(timeoutHandle)
          timeoutHandle = undefined
        }
      }
      const abort = () => {
        aborted = true
        clearRequestTimeout()
        controller.abort()
      }
      if (options.timeoutMs !== undefined && options.timeoutMs > 0) {
        timeoutHandle = setTimeout(() => {
          if (failed || aborted) return
          fail('request timed out')
          abort()
        }, options.timeoutMs)
      }
      const body = options.data === undefined
        ? undefined
        : typeof options.data === 'string' || options.data instanceof ArrayBuffer
          ? options.data
          : JSON.stringify(options.data)
      if (
        body
        && typeof options.data === 'object'
        && !(options.data instanceof ArrayBuffer)
        && !Object.keys(header).some((key) => key.toLowerCase() === 'content-type')
      ) {
        header['Content-Type'] = 'application/json'
      }
      const fetchOptions: RequestInit = {
        method: options.method ?? 'POST',
        headers: header,
        credentials: authRequest.credentials,
        signal: controller.signal,
      }
      if (body !== undefined) fetchOptions.body = body
      void fetch(url, fetchOptions).then(async (response) => {
        if (failed || aborted) return
        if (!response.ok) {
          clearRequestTimeout()
          let problem: unknown
          try { problem = await response.json() } catch { /* Non-JSON HTTP errors keep their status. */ }
          fail(responseProblemCode(problem) || `HTTP ${response.status}`)
          return
        }
        const reader = response.body?.getReader()
        if (!reader) {
          clearRequestTimeout()
          fail('streaming response is unavailable')
          return
        }
        try {
          while (true) {
            const chunk = await reader.read()
            if (chunk.done) break
            const value = chunk.value
            const buffer = value.buffer.slice(
              value.byteOffset,
              value.byteOffset + value.byteLength,
            ) as ArrayBuffer
            decoder.push(buffer).forEach((event) => emit(event, abort))
          }
          decoder.finish().forEach((event) => emit(event, abort))
          end()
        } catch (error) {
          if (!aborted) fail(errorMessage(error))
        } finally {
          clearRequestTimeout()
        }
      }).catch((error) => {
        clearRequestTimeout()
        if (!aborted) fail(errorMessage(error))
      })
      return { abort }
    }

    // Retain a bounded prefix for non-SSE problem responses on Mini chunked requests.
    const problemPrefix = new Uint8Array(16384)
    let problemBytes = 0
    const task = Taro.request<unknown>({
      url,
      method: options.method ?? 'POST',
      data: options.data,
      header,
      timeout: options.timeoutMs ?? 90000,
      credentials: authRequest.credentials,
      enableChunked: true,
      responseType: 'arraybuffer',
    }) as unknown as Promise<{ statusCode: number; data?: unknown }> & {
      abort?: () => void
      onChunkReceived?: (callback: (payload: { data: ArrayBuffer }) => void) => void
    }
    const abort = () => {
      aborted = true
      task.abort?.()
    }
    if (typeof task.onChunkReceived !== 'function') {
      fail('chunked response is unavailable')
      abort()
    } else {
      task.onChunkReceived(({ data }) => {
        if (failed || aborted || ended) return
        try {
          const prefix = new Uint8Array(data).subarray(0, problemPrefix.length - problemBytes)
          problemPrefix.set(prefix, problemBytes)
          problemBytes += prefix.length
          decoder.push(data).forEach((event) => emit(event, abort))
        } catch {
          fail('malformed SSE payload')
          abort()
        }
      })
    }
    void task.then((response) => {
      if (failed || aborted || ended) return
      if (response.statusCode < 200 || response.statusCode >= 300) {
        let problem = response.data
        try {
          if (problem instanceof ArrayBuffer) problem = utf8Decoder().decode(new Uint8Array(problem))
          if (problem === undefined || problem === '') {
            problem = utf8Decoder().decode(problemPrefix.subarray(0, problemBytes))
          }
          if (typeof problem === 'string') problem = JSON.parse(problem)
        } catch { /* Non-JSON HTTP errors keep their status. */ }
        fail(responseProblemCode(problem) || `HTTP ${response.statusCode}`)
        return
      }
      try {
        decoder.finish().forEach((event) => emit(event, abort))
        end()
      } catch {
        fail('malformed SSE payload')
        abort()
      }
    }).catch((error) => {
      if (!aborted) fail(errorMessage(error))
    })
    return { abort }
  }

  return { request, requestSse }
}
