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

import {
  clientAuthRequest,
  type ClientAuthContext,
} from './auth-context'
import type { ApiResult, ApiStreamTask, ApiTransport, RequestData } from './transport'


export const CHAT_STREAM_TIMEOUT_MS = 180000

export interface ChatRequestOptions {
  auth: ClientAuthContext
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
  create(request: ChatCreateRequest, options: ChatRequestOptions): Promise<ApiResult<ConversationSummary>>
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
      fallback: () => T
      validate: (value: unknown) => boolean
    },
  ): Promise<ApiResult<T>> => {
    const auth = clientAuthRequest(options.auth, { mutating: config.mutating })
    return transport.request(path, {
      ...(config.method === undefined ? {} : { method: config.method }),
      ...(data === undefined ? {} : { data }),
      header: auth.header,
      credentials: auth.credentials,
      baseUrl: auth.baseUrl,
      auth: false,
      attachAnalyticsHeaders: false,
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
        `/api/v2/chat/conversations${encoded ? `?${encoded}` : ''}`,
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
      const data = createRequest.title === undefined ? {} : { title: createRequest.title }
      return request('/api/v2/chat/conversations', data, options, {
        method: 'POST',
        mutating: true,
        fallback: emptyConversation,
        validate: isConversationSummary,
      })
    },

    get(conversationId, options) {
      const id = boundedIdentifier(conversationId, 'conversation id')
      return request(
        `/api/v2/chat/conversations/${encodeURIComponent(id)}`,
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
      const auth = clientAuthRequest(options.auth, { mutating: true })
      let rejected = false
      return requestSse(
        `/api/v2/chat/conversations/${encodeURIComponent(id)}/messages/stream`,
        {
          method: 'POST',
          data: {
            content: message.content,
            ...(clientMessageId === undefined ? {} : { clientMessageId }),
          },
          baseUrl: auth.baseUrl,
          credentials: auth.credentials,
          header: {
            ...auth.header,
            'Idempotency-Key': options.idempotencyKey,
          },
          timeoutMs: CHAT_STREAM_TIMEOUT_MS,
          onEvent: (event) => {
            if (rejected) return
            if (!isChatEventEnvelope(event)) {
              rejected = true
              options.onFailure('invalid chat stream event')
              return
            }
            options.onEvent(event)
          },
          onFailure: (error) => {
            if (rejected) return
            options.onFailure(streamFailureCode(error))
          },
        },
      )
    },
  }
}
