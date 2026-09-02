import { describe, expect, it, vi } from 'vitest'

import type {
  ApiResult,
  ChatClient,
  ChatStreamOptions,
  ClientAuthContext,
} from '@wow-mini/api-client'
import type {
  ChatEventEnvelope,
  ConversationDetail,
  ConversationPage,
  ConversationSummary,
} from '@wow-mini/domain'

import { ChatModel } from './chat-model'


const now = '2026-09-03T12:00:00.000Z'
const conversation: ConversationSummary = {
  id: '00000000-0000-4000-8000-000000000501',
  title: '元素萨满配装',
  status: 'active',
  createdAt: now,
  updatedAt: now,
}

function success<T>(payload: T): ApiResult<T> {
  return { payload, fromFallback: false, error: '', httpStatus: 200 }
}

class FakeChatClient implements ChatClient {
  detail: ConversationDetail = { ...conversation, messages: [] }
  readonly calls: Array<{ name: string; auth: ClientAuthContext }> = []
  streamOptions: ChatStreamOptions | null = null
  readonly abort = vi.fn()

  async list(
    _request: Parameters<ChatClient['list']>[0],
    options: Parameters<ChatClient['list']>[1],
  ): Promise<ApiResult<ConversationPage>> {
    this.calls.push({ name: 'list', auth: options.auth })
    return success({ items: [conversation], nextCursor: null })
  }

  async create(
    _request: Parameters<ChatClient['create']>[0],
    options: Parameters<ChatClient['create']>[1],
  ): Promise<ApiResult<ConversationSummary>> {
    this.calls.push({ name: 'create', auth: options.auth })
    return success(conversation)
  }

  async get(
    _conversationId: Parameters<ChatClient['get']>[0],
    options: Parameters<ChatClient['get']>[1],
  ): Promise<ApiResult<ConversationDetail>> {
    this.calls.push({ name: 'get', auth: options.auth })
    return success(this.detail)
  }

  streamMessage(
    _conversationId: Parameters<ChatClient['streamMessage']>[0],
    _request: Parameters<ChatClient['streamMessage']>[1],
    options: Parameters<ChatClient['streamMessage']>[2],
  ): ReturnType<ChatClient['streamMessage']> {
    this.calls.push({ name: 'stream', auth: options.auth })
    this.streamOptions = options
    return { abort: this.abort }
  }

  emit(event: ChatEventEnvelope): void {
    if (!this.streamOptions) throw new Error('stream not started')
    this.streamOptions.onEvent(event)
  }
}

const auth: ClientAuthContext = { kind: 'mini', accessToken: 'mini-token' }

describe('ChatModel', () => {
  it('loads server-owned conversations and the selected ordered detail', async () => {
    const client = new FakeChatClient()
    const model = new ChatModel(client, () => auth, { requestId: () => 'request-0001' })

    await model.load()

    expect(model.get().phase).toBe('ready')
    expect(model.get().conversations).toEqual([conversation])
    expect(model.get().activeConversation).toEqual(client.detail)
    expect(client.calls.map((call) => call.name)).toEqual(['list', 'get'])
    expect(client.calls.every((call) => call.auth === auth)).toBe(true)
  })

  it('sequence-checks streamed deltas and refreshes persisted history on completion', async () => {
    const client = new FakeChatClient()
    const model = new ChatModel(client, () => auth, {
      requestId: vi.fn()
        .mockReturnValueOnce('client-message-0001')
        .mockReturnValueOnce('idempotency-0001'),
    })
    await model.load()

    model.send('帮我分析这套装备')
    client.emit({
      type: 'started', requestId: 'server-request', conversationId: conversation.id,
      runId: 'run-1', sequence: 1,
    })
    client.emit({
      type: 'delta', requestId: 'server-request', conversationId: conversation.id,
      runId: 'run-1', sequence: 2, text: '先看',
    })
    client.emit({
      type: 'delta', requestId: 'server-request', conversationId: conversation.id,
      runId: 'run-1', sequence: 3, text: '属性。',
    })
    expect(model.get().streamText).toBe('先看属性。')
    expect(model.get().pendingUserContent).toBe('帮我分析这套装备')

    client.detail = {
      ...conversation,
      messages: [
        { id: 'message-1', role: 'user', content: '帮我分析这套装备', createdAt: now },
        { id: 'message-2', role: 'assistant', content: '先看属性。', createdAt: now },
      ],
    }
    client.emit({
      type: 'completed', requestId: 'server-request', conversationId: conversation.id,
      runId: 'run-1', sequence: 4, text: '先看属性。',
    })

    await vi.waitFor(() => expect(model.get().activeConversation?.messages).toHaveLength(2))
    expect(model.get().phase).toBe('ready')
    expect(model.get().pendingUserContent).toBe('')
    expect(client.calls.filter((call) => call.name === 'get')).toHaveLength(2)
  })

  it('aborts a sequence gap and never presents the partial stream as persisted history', async () => {
    const client = new FakeChatClient()
    const model = new ChatModel(client, () => auth, { requestId: () => 'request-0001' })
    await model.load()

    model.send('继续')
    client.emit({
      type: 'started', requestId: 'server-request', conversationId: conversation.id,
      runId: 'run-1', sequence: 1,
    })
    client.emit({
      type: 'delta', requestId: 'server-request', conversationId: conversation.id,
      runId: 'run-1', sequence: 3, text: '不可信片段',
    })

    expect(client.abort).toHaveBeenCalledOnce()
    expect(model.get()).toMatchObject({
      phase: 'blocked',
      errorCode: 'CHAT_SEQUENCE_GAP',
      streamText: '',
    })
    expect(model.get().activeConversation?.messages).toEqual([])
  })
})
