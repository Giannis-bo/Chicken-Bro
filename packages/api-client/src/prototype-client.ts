import {
  isPrototypeChatStreamEvent,
  isPrototypeConversationResponse,
  isPrototypeSimulationResponse,
  isPrototypeSessionResponse,
  isPrototypeSnapshotResponse,
  type PrototypeChatStreamEvent,
  type PrototypeConversationResponse,
  type PrototypeSimulationResponse,
  type PrototypeSessionResponse,
  type PrototypeSnapshotResponse,
} from '../../domain/src/prototype'

import type { ApiResult, ApiStreamTask, ApiTransport } from './transport'

export const PROTOTYPE_SESSION_STORAGE_KEY = 'chickenbro.web.prototype.session'
export const PROTOTYPE_CHAT_TIMEOUT_MS = 180000

function prototypeStreamFailureCode(error: string): string {
  return error === 'request timed out' ? 'CODEX_TIMEOUT' : error
}

export interface PrototypeWebClient {
  getSessionToken(): string
  createSession(): Promise<ApiResult<PrototypeSessionResponse>>
  resetSession(): Promise<ApiResult<{ revoked: boolean; requestId: string }>>
  createConversation(title?: string): Promise<ApiResult<PrototypeConversationResponse>>
  getConversation(conversationId: string): Promise<ApiResult<PrototypeConversationResponse>>
  resolveSnapshot(sourceUrl: string): Promise<ApiResult<PrototypeSnapshotResponse>>
  getSnapshot(snapshotId: string): Promise<ApiResult<PrototypeSnapshotResponse>>
  submitSimulation(
    snapshotId: string,
    scenario: Readonly<Record<string, unknown>>,
    idempotencyKey: string,
  ): Promise<ApiResult<PrototypeSimulationResponse>>
  getSimulation(jobId: string): Promise<ApiResult<PrototypeSimulationResponse>>
  streamMessage(
    conversationId: string,
    content: string,
    clientMessageId: string,
    idempotencyKey: string,
    handlers: {
      onEvent: (event: PrototypeChatStreamEvent) => void
      onFailure: (error: string) => void
    },
  ): ApiStreamTask
}

interface PrototypeStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

function browserStorage(): PrototypeStorage | undefined {
  if (typeof window === 'undefined') return undefined
  try {
    return window.sessionStorage
  } catch {
    return undefined
  }
}

function validToken(value: string | null | undefined): value is string {
  return Boolean(value && value.length >= 32 && value.length <= 512 && !/\s/u.test(value))
}

function sessionHeader(token: string): Readonly<Record<string, string>> {
  return token ? { 'X-Prototype-Session': token } : {}
}

function emptySession(): PrototypeSessionResponse {
  return { mode: 'prototype', sessionToken: '', expiresAt: '', requestId: '' }
}

function emptyConversation(): PrototypeConversationResponse {
  return {
    conversationId: '',
    title: '',
    status: 'active',
    createdAt: '',
    updatedAt: '',
    messages: [],
    requestId: '',
  }
}

function emptySnapshot(): PrototypeSnapshotResponse {
  return {
    snapshotId: '',
    provider: 'raiderio',
    sourceUrl: '',
    sourceKey: '',
    revision: 0,
    readiness: 'SNAPSHOT_UNAVAILABLE',
    blockers: [],
    snapshot: {},
    provenance: {},
    rawSha256: '',
    fetchedAt: '',
    requestId: '',
  }
}

function emptySimulation(): PrototypeSimulationResponse {
  return {
    jobId: '',
    snapshotId: '',
    status: 'failed',
    scenarioHash: '',
    compilerRevision: '',
    runtimeRevision: '',
    errorCode: 'SIMULATION_UNAVAILABLE',
    createdAt: '',
    updatedAt: '',
    requestId: '',
  }
}

function emptyRevoke(): { revoked: boolean; requestId: string } {
  return { revoked: false, requestId: '' }
}

export function createPrototypeWebClient(
  transport: ApiTransport,
  storage: PrototypeStorage | undefined = browserStorage(),
  ): PrototypeWebClient {
  const readToken = (): string => {
    try {
      const token = storage?.getItem(PROTOTYPE_SESSION_STORAGE_KEY)
      return validToken(token) ? token : ''
    } catch {
      return ''
    }
  }

  const writeToken = (token: string): void => {
    try {
      if (storage) storage.setItem(PROTOTYPE_SESSION_STORAGE_KEY, token)
    } catch {
      // A private browsing context may reject storage. The server response still
      // remains untrusted and the UI will ask the user to retry in a normal tab.
    }
  }

  const clearToken = (): void => {
    try {
      storage?.removeItem(PROTOTYPE_SESSION_STORAGE_KEY)
    } catch {
      // Clearing is best-effort; no formal auth storage is touched here.
    }
  }

  const request = <T>(
    path: string,
    options: {
      method?: 'GET' | 'POST'
      data?: Readonly<Record<string, unknown>>
      fallback: () => T
      validate: (value: unknown) => boolean
    },
  ): Promise<ApiResult<T>> => transport.request(path, {
    ...(options.method === undefined ? {} : { method: options.method }),
    ...(options.data === undefined ? {} : { data: options.data }),
    header: sessionHeader(readToken()),
    auth: false,
    baseUrl: 'web-auth',
    credentials: 'omit',
    attachAnalyticsHeaders: false,
    responseMode: 'structured-problem',
    fallback: options.fallback,
    validate: options.validate,
  })

  return {
    getSessionToken: readToken,

    async createSession() {
      const result = await request('/api/v2/prototype/sessions', {
        method: 'POST',
        fallback: emptySession,
        validate: isPrototypeSessionResponse,
      })
      if (!result.fromFallback && isPrototypeSessionResponse(result.payload)) writeToken(result.payload.sessionToken)
      return result
    },

    async resetSession() {
      const result = await request('/api/v2/prototype/sessions/revoke', {
        method: 'POST',
        fallback: emptyRevoke,
        validate: (value): value is { revoked: boolean; requestId: string } => (
          typeof value === 'object'
          && value !== null
          && 'revoked' in value
          && value.revoked === true
          && 'requestId' in value
          && typeof value.requestId === 'string'
        ),
      })
      clearToken()
      return result
    },

    createConversation(title = '炸鸡队长对话') {
      return request('/api/v2/prototype/conversations', {
        method: 'POST',
        data: { title },
        fallback: emptyConversation,
        validate: isPrototypeConversationResponse,
      })
    },

    getConversation(conversationId) {
      return request(`/api/v2/prototype/conversations/${encodeURIComponent(conversationId)}`, {
        fallback: emptyConversation,
        validate: isPrototypeConversationResponse,
      })
    },

    resolveSnapshot(sourceUrl) {
      return request('/api/v2/prototype/source-snapshots', {
        method: 'POST',
        data: { sourceUrl },
        fallback: emptySnapshot,
        validate: isPrototypeSnapshotResponse,
      })
    },

    getSnapshot(snapshotId) {
      return request(`/api/v2/prototype/source-snapshots/${encodeURIComponent(snapshotId)}`, {
        fallback: emptySnapshot,
        validate: isPrototypeSnapshotResponse,
      })
    },

    submitSimulation(snapshotId, scenario, idempotencyKey) {
      return transport.request('/api/v2/prototype/simulations', {
        method: 'POST',
        data: { snapshotId, scenario },
        header: {
          ...sessionHeader(readToken()),
          'Idempotency-Key': idempotencyKey,
        },
        auth: false,
        baseUrl: 'web-auth',
        credentials: 'omit',
        attachAnalyticsHeaders: false,
        responseMode: 'structured-problem',
        fallback: emptySimulation,
        validate: isPrototypeSimulationResponse,
      })
    },

    getSimulation(jobId) {
      return request(`/api/v2/prototype/simulations/${encodeURIComponent(jobId)}`, {
        fallback: emptySimulation,
        validate: isPrototypeSimulationResponse,
      })
    },

    streamMessage(conversationId, content, clientMessageId, idempotencyKey, handlers) {
      const requestSse = transport.requestSse
      if (!requestSse) {
        handlers.onFailure('SSE transport is unavailable')
        return { abort() {} }
      }
      return requestSse(`/api/v2/prototype/conversations/${encodeURIComponent(conversationId)}/messages/stream`, {
        method: 'POST',
        data: { content, clientMessageId },
        baseUrl: 'web-auth',
        header: {
          ...sessionHeader(readToken()),
          'Idempotency-Key': idempotencyKey,
        },
        timeoutMs: PROTOTYPE_CHAT_TIMEOUT_MS,
        onEvent: (event) => {
          if (!isPrototypeChatStreamEvent(event)) {
            handlers.onFailure('invalid prototype stream event')
            return
          }
          handlers.onEvent(event)
        },
        onFailure: (error) => handlers.onFailure(prototypeStreamFailureCode(error)),
      })
    },
  }
}
