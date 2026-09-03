import {
  isChatEventEnvelope,
  isConversationDetail,
  isConversationPage,
  isConversationSummary,
  isValidIdempotencyKey,
  type ChatEventEnvelope,
  type ConversationDetail,
  type ConversationPage,
  type ConversationSummary,
} from '@wow-mini/domain'

import type { ClientAuthContext } from './auth-context'
import type { ApiResult, ApiStreamTask, ApiTransport, RequestData } from './transport'
import { apiV2Path } from './api-v2-prefix'


export const CHAT_STREAM_TIMEOUT_MS = 180000

export interface ChatRequestOptions {
  auth: ClientAuthContext
}

export interface ChatCreateOptions extends ChatRequestOptions {
  idempotencyKey: string
}

export interface ChatListRequest {
  cursor?: string
  limit?: number
}

export interface ChatCreateRequest {
  title?: string
}

export interface ChatMessageRequest {
  content: string
  clientMessageId?: string
}

export interface ChatStreamOptions extends ChatRequestOptions {
  idempotencyKey: string
  onEvent: (event: ChatEventEnvelope) => void
  onFailure: (error: string) => void
}

export interface ChatClient {
  list(request: ChatListRequest, options: ChatRequestOptions): Promise<ApiResult<ConversationPage>>
  create(request: ChatCreateRequest, options: ChatCreateOptions): Promise<ApiResult<ConversationSummary>>
  get(conversationId: string, options: ChatRequestOptions): Promise<ApiResult<ConversationDetail>>
  streamMessage(
    conversationId: string,
    request: ChatMessageRequest,
    options: ChatStreamOptions,
  ): ApiStreamTask
}


function emptyConversation(): ConversationSummary {
  return { id: '', title: '', status: 'active', createdAt: '', updatedAt: '' }
}

function emptyConversationPage(): ConversationPage {
  return { items: [], nextCursor: null }
}

function emptyConversationDetail(): ConversationDetail {
  return { ...emptyConversation(), messages: [] }
}

function boundedIdentifier(value: string, label: string): string {
  const normalized = value.trim()
  if (!normalized || normalized.length > 128 || /\s/u.test(normalized)) {
    throw new TypeError(`${label} is invalid`)
  }
  return normalized
}

function streamFailureCode(error: string): string {
  return error === 'request timed out' ? 'CODEX_TIMEOUT' : error
}

export function createChatClient(transport: ApiTransport): ChatClient {
  const request = <T>(
    path: string,
    data: RequestData | undefined,
    options: ChatRequestOptions,
    config: {
      method?: 'GET' | 'POST'
      mutating: boolean
      idempotencyKey?: string
      fallback: () => T
      validate: (value: unknown) => boolean
    },
  ): Promise<ApiResult<T>> => {
    return transport.request(path, {
      ...(config.method === undefined ? {} : { method: config.method }),
      ...(data === undefined ? {} : { data }),
      ...(config.idempotencyKey === undefined
        ? {}
        : { header: { 'Idempotency-Key': config.idempotencyKey } }),
      auth: options.auth,
      responseMode: 'structured-problem',
      fallback: config.fallback,
      validate: config.validate,
    })
  }

  return {
    list(listRequest, options) {
      const query = new URLSearchParams()
      if (listRequest.cursor !== undefined) query.set('cursor', listRequest.cursor)
      if (listRequest.limit !== undefined) query.set('limit', String(listRequest.limit))
      const encoded = query.toString()
      return request(
        apiV2Path(`/chat/conversations${encoded ? `?${encoded}` : ''}`),
        undefined,
        options,
        {
          mutating: false,
          fallback: emptyConversationPage,
          validate: isConversationPage,
        },
      )
    },

    create(createRequest, options) {
      if (!isValidIdempotencyKey(options.idempotencyKey)) {
        throw new TypeError('idempotency key is invalid')
      }
      const data = createRequest.title === undefined ? {} : { title: createRequest.title }
      return request(apiV2Path('/chat/conversations'), data, options, {
        method: 'POST',
        mutating: true,
        idempotencyKey: options.idempotencyKey,
        fallback: emptyConversation,
        validate: isConversationSummary,
      })
    },

    get(conversationId, options) {
      const id = boundedIdentifier(conversationId, 'conversation id')
      return request(
        apiV2Path(`/chat/conversations/${encodeURIComponent(id)}`),
        undefined,
        options,
        {
          mutating: false,
          fallback: emptyConversationDetail,
          validate: isConversationDetail,
        },
      )
    },

    streamMessage(conversationId, message, options) {
      const requestSse = transport.requestSse?.bind(transport)
      if (!requestSse) {
        options.onFailure('SSE transport is unavailable')
        return { abort() {} }
      }
      let id: string
      let clientMessageId: string | undefined
      try {
        id = boundedIdentifier(conversationId, 'conversation id')
        if (!message.content.trim() || message.content.length > 4000) {
          throw new TypeError('message content is invalid')
        }
        if (message.clientMessageId !== undefined) {
          clientMessageId = boundedIdentifier(message.clientMessageId, 'client message id')
        }
        if (!isValidIdempotencyKey(options.idempotencyKey)) {
          throw new TypeError('idempotency key is invalid')
        }
      } catch (error) {
        options.onFailure(error instanceof Error ? error.message : 'invalid Chat request')
        return { abort() {} }
      }
      let rejected = false
      let terminalSeen = false
      return requestSse(
        apiV2Path(`/chat/conversations/${encodeURIComponent(id)}/messages/stream`),
        {
          method: 'POST',
          data: {
            content: message.content,
            ...(clientMessageId === undefined ? {} : { clientMessageId }),
          },
          auth: options.auth,
          header: {
            'Idempotency-Key': options.idempotencyKey,
          },
          timeoutMs: CHAT_STREAM_TIMEOUT_MS,
          onEvent: (event) => {
            if (rejected) return
            if (!isChatEventEnvelope(event)) {
              rejected = true
              options.onFailure('invalid chat stream event')
              throw new Error('invalid chat stream event')
            }
            terminalSeen = event.type === 'completed' || event.type === 'failed'
              ? true
              : terminalSeen
            options.onEvent(event)
          },
          onFailure: (error) => {
            if (rejected) return
            options.onFailure(streamFailureCode(error))
          },
          onEnd: () => {
            if (rejected || terminalSeen) return
            rejected = true
            options.onFailure('chat stream ended before a terminal event')
          },
        },
      )
    },
  }
}
