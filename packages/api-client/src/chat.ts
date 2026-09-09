import {
  isChatImage,
  type ChatImage,
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


// Allow the server's 480-second analysis deadline to emit its terminal event.
export const CHAT_STREAM_TIMEOUT_MS = 510000

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
  imageIds?: readonly string[]
  content: string
  clientMessageId?: string
}

export interface ChatStreamOptions extends ChatRequestOptions {
  idempotencyKey: string
  onEvent: (event: ChatEventEnvelope) => void
  onFailure: (error: string) => void
}

export interface ChatClient {
  imageCapabilities(options: ChatRequestOptions): Promise<ApiResult<{enabled: boolean; maxImages: number; maxBytes: number}>>
  uploadImage(body: {dataUrl: string}, options: ChatCreateOptions): Promise<ApiResult<ChatImage>>
  getImage(id: string, options: ChatRequestOptions): Promise<ApiResult<{dataUrl: string}>>
  removeImage(id: string, options: ChatRequestOptions): Promise<ApiResult<{deleted: boolean}>>
  setFeedback(conversationId: string, messageId: string, resolved: boolean,
    options: ChatRequestOptions): Promise<ApiResult<{ resolved: boolean }>>
  remove(conversationId: string, options: ChatRequestOptions): Promise<ApiResult<{ deleted: boolean }>>
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
      method?: 'GET' | 'POST' | 'DELETE'
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
    imageCapabilities(options) {
      return request(apiV2Path('/chat/image-capabilities'), undefined, options, {
        mutating: false, fallback: () => ({enabled: false, maxImages: 3, maxBytes: 5242880}),
        validate: value => typeof value === 'object' && value !== null && 'enabled' in value
          && typeof value.enabled === 'boolean' && 'maxImages' in value && value.maxImages === 3
          && 'maxBytes' in value && value.maxBytes === 5242880,
      })
    },
    uploadImage(body, options) {
      if (!isValidIdempotencyKey(options.idempotencyKey)) throw new TypeError('idempotency key is invalid')
      if (!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+=*$/u.test(body.dataUrl)
        || body.dataUrl.length > 6990532) throw new TypeError('请选择不超过 5 MiB 的 PNG/JPEG 图片')
      return request(apiV2Path('/chat/images'), body, options, {
        method: 'POST', mutating: true, idempotencyKey: options.idempotencyKey,
        fallback: () => ({id: '', mimeType: 'image/png', width: 0, height: 0}), validate: isChatImage,
      })
    },
    getImage(imageId, options) {
      const id = boundedIdentifier(imageId, 'image id')
      return request(apiV2Path('/chat/images/' + encodeURIComponent(id)), undefined, options, {
        mutating: false, fallback: () => ({dataUrl: ''}),
        validate: value => typeof value === 'object' && value !== null && 'dataUrl' in value
          && typeof value.dataUrl === 'string' && /^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+=*$/u.test(value.dataUrl)
          && value.dataUrl.length <= 6990532,
      })
    },
    removeImage(imageId, options) {
      const id = boundedIdentifier(imageId, 'image id')
      return request(apiV2Path('/chat/images/' + encodeURIComponent(id)), undefined, options, {
        method: 'DELETE', mutating: true, fallback: () => ({deleted: false}),
        validate: value => typeof value === 'object' && value !== null && 'deleted' in value && value.deleted === true,
      })
    },
    setFeedback(conversationId, messageId, resolved, options) {
      const id = boundedIdentifier(conversationId, 'conversation id')
      const message = boundedIdentifier(messageId, 'message id')
      if (typeof resolved !== 'boolean') throw new TypeError('feedback is invalid')
      return request(apiV2Path(`/chat/conversations/${encodeURIComponent(id)}/messages/${encodeURIComponent(message)}/feedback`),
        { resolved }, options, {
          method: 'POST', mutating: true, fallback: () => ({ resolved }),
          validate: value => typeof value === 'object' && value !== null
            && Object.keys(value).length === 1 && 'resolved' in value && value.resolved === resolved,
        })
    },
    remove(conversationId, options) {
      const id = boundedIdentifier(conversationId, 'conversation id')
      return request(apiV2Path(`/chat/conversations/${encodeURIComponent(id)}`), undefined, options, {
        method: 'DELETE', mutating: true, fallback: () => ({ deleted: false }),
        validate: value => typeof value === 'object' && value !== null && 'deleted' in value && value.deleted === true,
      })
    },
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
        apiV2Path(`/chat/conversations/${encodeURIComponent(id)}?includeProgress=true&includeFeedback=true&includeImages=true`),
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
        if (message.imageIds !== undefined && (!Array.isArray(message.imageIds)
          || message.imageIds.length < 1 || message.imageIds.length > 3
          || new Set(message.imageIds).size !== message.imageIds.length
          || message.imageIds.some(imageId => boundedIdentifier(imageId, 'image id') !== imageId))) {
          throw new TypeError('message images are invalid')
        }
        if ((!message.content.trim() && !message.imageIds?.length) || message.content.length > 4000) {
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
        apiV2Path(`/chat/conversations/${encodeURIComponent(id)}/messages/stream?includeProgress=true`),
        {
          method: 'POST',
          data: {
            content: message.content,
            ...(message.imageIds?.length ? {imageIds: [...message.imageIds]} : {}),
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
