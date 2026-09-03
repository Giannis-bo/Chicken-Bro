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
const otherConversation: ConversationSummary = {
  ...conversation,
  id: '00000000-0000-4000-8000-000000000502',
  title: '另一个会话',
}

function success<T>(payload: T): ApiResult<T> {
  return { payload, fromFallback: false, error: '', httpStatus: 200 }
}

class FakeChatClient implements ChatClient {
  detail: ConversationDetail = { ...conversation, messages: [] }
  readonly calls: Array<{ name: string; auth: ClientAuthContext; idempotencyKey?: string }> = []
  createFailures = 0
  streamFailure = ''
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
    this.calls.push({
      name: 'create',
      auth: options.auth,
      idempotencyKey: options.idempotencyKey,
    })
    if (this.createFailures > 0) {
      this.createFailures -= 1
      return {
        payload: conversation,
        fromFallback: true,
        error: 'network interrupted',
        httpStatus: 0,
      }
    }
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
    if (this.streamFailure) options.onFailure(this.streamFailure)
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

  it('reuses one conversation creation identity after an uncertain transport failure', async () => {
    const client = new FakeChatClient()
    client.createFailures = 1
    const requestId = vi.fn()
      .mockReturnValueOnce('create-request-0001')
      .mockReturnValueOnce('unexpected-second-key')
    const model = new ChatModel(client, () => auth, { requestId })

    await expect(model.create('  新对话  ')).resolves.toBeNull()
    await expect(model.create('新对话')).resolves.toEqual(conversation)

    const creates = client.calls.filter((call) => call.name === 'create')
    expect(creates).toHaveLength(2)
    expect(creates.map((call) => call.idempotencyKey)).toEqual([
      'create-request-0001',
      'create-request-0001',
    ])
    expect(requestId).toHaveBeenCalledOnce()
  })

  it('coalesces concurrent conversation creation into one server mutation', async () => {
    const client = new FakeChatClient()
    let finish!: (result: ApiResult<ConversationSummary>) => void
    client.create = vi.fn((_request, options) => {
      client.calls.push({
        name: 'create',
        auth: options.auth,
        idempotencyKey: options.idempotencyKey,
      })
      return new Promise<ApiResult<ConversationSummary>>((resolve) => { finish = resolve })
    })
    const model = new ChatModel(client, () => auth, { requestId: () => 'create-request-0001' })

    const first = model.create()
    const second = model.create()
    expect(client.calls.filter((call) => call.name === 'create')).toHaveLength(1)
    finish(success(conversation))

    await expect(first).resolves.toEqual(conversation)
    await expect(second).resolves.toEqual(conversation)
    expect(client.calls.filter((call) => call.name === 'create')).toHaveLength(1)
  })

  it('does not select a created conversation over a newer explicit selection', async () => {
    const client = new FakeChatClient()
    let finishCreate!: (result: ApiResult<ConversationSummary>) => void
    client.create = vi.fn((_request, options) => {
      client.calls.push({ name: 'create', auth: options.auth, idempotencyKey: options.idempotencyKey })
      return new Promise<ApiResult<ConversationSummary>>((resolve) => { finishCreate = resolve })
    })
    client.get = vi.fn(async (conversationId, options) => {
      client.calls.push({ name: 'get', auth: options.auth })
      const selected = conversationId === otherConversation.id ? otherConversation : conversation
      return success({ ...selected, messages: [] })
    })
    const model = new ChatModel(client, () => auth, { requestId: () => 'create-request-0001' })

    const creation = model.create()
    await model.open(otherConversation.id)
    finishCreate(success(conversation))
    await creation

    expect(model.get().activeConversation?.id).toBe(otherConversation.id)
    expect(model.get().conversations).toContainEqual(conversation)
  })

  it('keeps the latest selected conversation when an older detail arrives last', async () => {
    const client = new FakeChatClient()
    const finishes = new Map<string, (result: ApiResult<ConversationDetail>) => void>()
    client.get = vi.fn((conversationId, options) => {
      client.calls.push({ name: 'get', auth: options.auth })
      return new Promise<ApiResult<ConversationDetail>>((resolve) => {
        finishes.set(conversationId, resolve)
      })
    })
    const model = new ChatModel(client, () => auth)

    const first = model.open(conversation.id)
    const second = model.open(otherConversation.id)
    finishes.get(otherConversation.id)?.(success({ ...otherConversation, messages: [] }))
    await second
    finishes.get(conversation.id)?.(success({ ...conversation, messages: [] }))
    await first

    expect(model.get().activeConversation?.id).toBe(otherConversation.id)
  })

  it('keeps the latest full history load when an older list arrives last', async () => {
    const client = new FakeChatClient()
    const finishes: Array<(result: ApiResult<ConversationPage>) => void> = []
    client.list = vi.fn((_request, options) => {
      client.calls.push({ name: 'list', auth: options.auth })
      return new Promise<ApiResult<ConversationPage>>((resolve) => { finishes.push(resolve) })
    })
    client.get = vi.fn(async (conversationId, options) => {
      client.calls.push({ name: 'get', auth: options.auth })
      const selected = conversationId === otherConversation.id ? otherConversation : conversation
      return success({ ...selected, messages: [] })
    })
    const model = new ChatModel(client, () => auth)

    const first = model.load()
    const second = model.load()
    finishes[1]?.(success({ items: [otherConversation], nextCursor: null }))
    await second
    finishes[0]?.(success({ items: [conversation], nextCursor: null }))
    await first

    expect(model.get().conversations).toEqual([otherConversation])
    expect(model.get().activeConversation?.id).toBe(otherConversation.id)
  })

  it('does not let an older pagination failure block a newer conversation selection', async () => {
    const client = new FakeChatClient()
    client.list = vi.fn(async (_request, options) => {
      client.calls.push({ name: 'list', auth: options.auth })
      return success({ items: [conversation], nextCursor: 'next-page' })
    })
    client.get = vi.fn(async (conversationId, options) => {
      client.calls.push({ name: 'get', auth: options.auth })
      const selected = conversationId === otherConversation.id ? otherConversation : conversation
      return success({ ...selected, messages: [] })
    })
    const model = new ChatModel(client, () => auth)
    await model.load()
    let finishMore!: (result: ApiResult<ConversationPage>) => void
    client.list = vi.fn((_request, options) => {
      client.calls.push({ name: 'list', auth: options.auth })
      return new Promise<ApiResult<ConversationPage>>((resolve) => { finishMore = resolve })
    })

    const pagination = model.loadMore()
    await model.open(otherConversation.id)
    finishMore({
      payload: { items: [], nextCursor: null },
      fromFallback: true,
      error: '旧分页请求失败',
      problemCode: 'CHAT_REQUEST_FAILED',
      httpStatus: 0,
    })
    await pagination

    expect(model.get()).toMatchObject({
      phase: 'ready',
      activeConversation: { id: otherConversation.id },
      errorCode: '',
    })
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

  it('coalesces rapid duplicate send taps into one stream mutation', async () => {
    const client = new FakeChatClient()
    const model = new ChatModel(client, () => auth, {
      requestId: vi.fn()
        .mockReturnValueOnce('client-message-0001')
        .mockReturnValueOnce('idempotency-0001'),
    })
    await model.load()

    const first = model.send('只发送一次')
    const second = model.send('只发送一次')

    expect(first).not.toBeNull()
    expect(second).toBe(first)
    expect(client.calls.filter((call) => call.name === 'stream')).toHaveLength(1)
    expect(client.abort).not.toHaveBeenCalled()
  })

  it('does not retain a stale stream handle after a synchronous transport failure', async () => {
    const client = new FakeChatClient()
    client.streamFailure = 'missing api base url'
    const model = new ChatModel(client, () => auth, { requestId: () => 'request-0001' })
    await model.load()

    model.send('第一次')
    client.streamFailure = ''
    const retried = model.send('第二次')

    expect(retried).not.toBeNull()
    expect(client.calls.filter((call) => call.name === 'stream')).toHaveLength(2)
    expect(client.abort).not.toHaveBeenCalled()
  })

  it('does not let an older recovery response overwrite a newer stream', async () => {
    const client = new FakeChatClient()
    const model = new ChatModel(client, () => auth, { requestId: () => 'request-0001' })
    await model.load()
    let finishRecovery!: (result: ApiResult<ConversationDetail>) => void
    client.get = vi.fn((_conversationId, options) => {
      client.calls.push({ name: 'get', auth: options.auth })
      return new Promise<ApiResult<ConversationDetail>>((resolve) => { finishRecovery = resolve })
    })

    client.streamFailure = 'connection interrupted'
    model.send('旧请求')
    client.streamFailure = ''
    model.send('新请求')
    finishRecovery(success(client.detail))
    await Promise.resolve()

    expect(model.get()).toMatchObject({
      phase: 'sending',
      pendingUserContent: '新请求',
      errorCode: '',
    })
  })
})
