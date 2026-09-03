import type {
  ApiResult,
  ApiStreamTask,
  ChatClient,
  ClientAuthContext,
} from '@wow-mini/api-client'
import type {
  ChatEventEnvelope,
  ConversationDetail,
  ConversationSummary,
} from '@wow-mini/domain'


export type ChatModelPhase = 'idle' | 'loading' | 'ready' | 'sending' | 'signed_out' | 'blocked'

export interface ChatModelState {
  phase: ChatModelPhase
  conversations: readonly ConversationSummary[]
  nextCursor: string | null
  activeConversation: ConversationDetail | null
  pendingUserContent: string
  streamText: string
  errorCode: string
  errorMessage: string
  retryable: boolean
}

export interface ChatModelDependencies {
  requestId?: () => string
}

type ChatListener = (state: ChatModelState) => void

const initialState: ChatModelState = {
  phase: 'idle',
  conversations: [],
  nextCursor: null,
  activeConversation: null,
  pendingUserContent: '',
  streamText: '',
  errorCode: '',
  errorMessage: '',
  retryable: false,
}

let fallbackRequestSequence = 0

function defaultRequestId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  fallbackRequestSequence += 1
  return `request-${Date.now()}-${fallbackRequestSequence}`
}

function boundedRequestId(value: string, prefix: string): string {
  const normalized = value.replace(/[^A-Za-z0-9._~-]/gu, '-').slice(0, 96)
  return normalized.length >= 8 ? normalized : `${prefix}-${normalized || 'request'}`
}

function resultProblem(result: ApiResult<unknown>, fallback: string): { code: string; message: string } {
  return {
    code: result.problemCode || 'CHAT_REQUEST_FAILED',
    message: result.error || fallback,
  }
}

export class ChatModel {
  private state: ChatModelState = initialState
  private readonly listeners = new Set<ChatListener>()
  private readonly requestId: () => string
  private activeStream: ApiStreamTask | null = null
  private streamSequence = 0
  private streamRequestId = ''
  private streamRunId = ''
  private streamGeneration = 0
  private pendingCreate: { title: string; idempotencyKey: string } | null = null

  constructor(
    private readonly client: ChatClient,
    private readonly authProvider: () => ClientAuthContext,
    dependencies: ChatModelDependencies = {},
  ) {
    this.requestId = dependencies.requestId ?? defaultRequestId
  }

  get(): ChatModelState {
    return this.state
  }

  subscribe(listener: ChatListener): () => void {
    this.listeners.add(listener)
    listener(this.state)
    return () => this.listeners.delete(listener)
  }

  async load(): Promise<void> {
    this.update({ phase: 'loading', errorCode: '', errorMessage: '', retryable: false })
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    const result = await this.client.list({ limit: 20 }, { auth })
    if (result.fromFallback) {
      this.apiFailure(result, '会话历史加载失败')
      return
    }
    const conversations = [...result.payload.items]
    this.update({
      phase: 'ready',
      conversations,
      nextCursor: result.payload.nextCursor,
      activeConversation: null,
      pendingUserContent: '',
      streamText: '',
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    const first = conversations[0]
    if (first) await this.open(first.id)
  }

  async loadMore(): Promise<void> {
    if (!this.state.nextCursor) return
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    const result = await this.client.list(
      { cursor: this.state.nextCursor, limit: 20 },
      { auth },
    )
    if (result.fromFallback) {
      this.apiFailure(result, '更多会话加载失败')
      return
    }
    const byId = new Map(this.state.conversations.map((item) => [item.id, item]))
    result.payload.items.forEach((item) => byId.set(item.id, item))
    this.update({
      phase: 'ready',
      conversations: [...byId.values()],
      nextCursor: result.payload.nextCursor,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
  }

  async open(conversationId: string): Promise<void> {
    this.activeStream?.abort()
    this.activeStream = null
    this.streamGeneration += 1
    this.update({ phase: 'loading', pendingUserContent: '', streamText: '' })
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    const result = await this.client.get(conversationId, { auth })
    if (result.fromFallback) {
      this.apiFailure(result, '会话内容加载失败')
      return
    }
    this.update({
      phase: 'ready',
      activeConversation: result.payload,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
  }

  async create(title?: string): Promise<ConversationSummary | null> {
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return null
    }
    const normalizedTitle = title?.trim() ?? ''
    const pending = this.pendingCreate?.title === normalizedTitle
      ? this.pendingCreate
      : {
          title: normalizedTitle,
          idempotencyKey: boundedRequestId(this.requestId(), 'conversation'),
        }
    this.pendingCreate = pending
    this.update({ phase: 'loading', errorCode: '', errorMessage: '', retryable: false })
    const result = await this.client.create(
      normalizedTitle ? { title: normalizedTitle } : {},
      { auth, idempotencyKey: pending.idempotencyKey },
    )
    if (result.fromFallback) {
      this.apiFailure(result, '新建会话失败')
      return null
    }
    if (this.pendingCreate === pending) this.pendingCreate = null
    const conversations = [
      result.payload,
      ...this.state.conversations.filter((item) => item.id !== result.payload.id),
    ]
    this.update({ conversations })
    await this.open(result.payload.id)
    return result.payload
  }

  send(content: string): ApiStreamTask | null {
    if (this.state.phase === 'sending') return this.activeStream
    const conversation = this.state.activeConversation
    const normalized = content.trim()
    if (!conversation || !normalized) {
      this.fail('CHAT_MESSAGE_REQUIRED', '请选择会话并输入消息', false)
      return null
    }
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return null
    }
    const generation = this.streamGeneration + 1
    this.streamGeneration = generation
    this.streamSequence = 0
    this.streamRequestId = ''
    this.streamRunId = ''
    this.update({
      phase: 'sending',
      pendingUserContent: normalized,
      streamText: '',
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    const clientMessageId = boundedRequestId(this.requestId(), 'client-message')
    const idempotencyKey = boundedRequestId(this.requestId(), 'idempotency')
    let endedDuringStart = false
    const task = this.client.streamMessage(
      conversation.id,
      { content: normalized, clientMessageId },
      {
        auth,
        idempotencyKey,
        onEvent: (event) => {
          if (event.type === 'completed' || event.type === 'failed') endedDuringStart = true
          this.onStreamEvent(event, conversation.id, generation)
          if (this.state.phase !== 'sending') endedDuringStart = true
        },
        onFailure: (error) => {
          endedDuringStart = true
          this.onStreamFailure(error, conversation.id, generation)
        },
      },
    )
    if (endedDuringStart) return null
    this.activeStream = task
    return task
  }

  async recover(): Promise<void> {
    const conversationId = this.state.activeConversation?.id
    if (conversationId) {
      await this.open(conversationId)
      return
    }
    await this.load()
  }

  dispose(): void {
    this.activeStream?.abort()
    this.activeStream = null
    this.streamGeneration += 1
    this.listeners.clear()
  }

  private onStreamEvent(event: ChatEventEnvelope, conversationId: string, generation: number): void {
    if (generation !== this.streamGeneration) return
    const expectedSequence = this.streamSequence + 1
    const firstEventInvalid = this.streamSequence === 0 && event.type !== 'started'
    const identityInvalid = event.conversationId !== conversationId
      || (this.streamRequestId !== '' && event.requestId !== this.streamRequestId)
      || (this.streamRunId !== '' && event.runId !== this.streamRunId)
    if (firstEventInvalid || identityInvalid || event.sequence !== expectedSequence) {
      this.activeStream?.abort()
      this.activeStream = null
      this.fail('CHAT_SEQUENCE_GAP', '回答流顺序异常，已重新读取服务端历史', true)
      void this.refreshAfterStream(conversationId, true, generation)
      return
    }
    this.streamSequence = event.sequence
    this.streamRequestId ||= event.requestId
    this.streamRunId ||= event.runId
    if (event.type === 'delta') {
      this.update({ streamText: this.state.streamText + event.text })
      return
    }
    if (event.type === 'completed') {
      this.activeStream = null
      this.update({ streamText: event.text })
      void this.refreshAfterStream(conversationId, false, generation)
      return
    }
    if (event.type === 'failed') {
      this.activeStream = null
      this.fail(event.errorCode, '本次回答未完成，用户消息已保留', event.retryable)
      void this.refreshAfterStream(conversationId, true, generation)
    }
  }

  private onStreamFailure(error: string, conversationId: string, generation: number): void {
    if (generation !== this.streamGeneration) return
    this.activeStream = null
    this.fail(error || 'CHAT_STREAM_FAILED', '回答连接中断，正在恢复服务端历史', true)
    void this.refreshAfterStream(conversationId, true, generation)
  }

  private async refreshAfterStream(
    conversationId: string,
    preserveFailure: boolean,
    generation: number,
  ): Promise<void> {
    if (generation !== this.streamGeneration) return
    const failure = {
      errorCode: this.state.errorCode,
      errorMessage: this.state.errorMessage,
      retryable: this.state.retryable,
    }
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    const result = await this.client.get(conversationId, { auth })
    if (generation !== this.streamGeneration) return
    if (result.fromFallback) {
      this.apiFailure(result, '服务端会话恢复失败')
      return
    }
    this.update({
      phase: preserveFailure ? 'blocked' : 'ready',
      activeConversation: result.payload,
      pendingUserContent: '',
      streamText: '',
      ...(preserveFailure
        ? failure
        : { errorCode: '', errorMessage: '', retryable: false }),
    })
  }

  private apiFailure(result: ApiResult<unknown>, fallback: string): void {
    const problem = resultProblem(result, fallback)
    if (problem.code === 'AUTH_REQUIRED' || result.httpStatus === 401) {
      this.update({
        phase: 'signed_out',
        errorCode: 'AUTH_REQUIRED',
        errorMessage: '小程序登录已失效，请重新登录',
        retryable: true,
      })
      return
    }
    this.fail(problem.code, problem.message, true)
  }

  private authFailure(error: unknown): void {
    this.update({
      phase: 'signed_out',
      errorCode: error instanceof Error ? error.message : 'MINI_SESSION_REQUIRED',
      errorMessage: '小程序登录已失效，请重新登录',
      retryable: true,
    })
  }

  private fail(code: string, message: string, retryable: boolean): void {
    this.update({
      phase: 'blocked',
      errorCode: code,
      errorMessage: message,
      retryable,
      streamText: '',
    })
  }

  private update(patch: Partial<ChatModelState>): void {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener(this.state))
  }
}
