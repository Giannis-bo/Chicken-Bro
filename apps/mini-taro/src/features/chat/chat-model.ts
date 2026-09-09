import type {
  ApiResult,
  ApiStreamTask,
  ChatClient,
  ClientAuthContext,
} from '@wow-mini/api-client'
import type {
  ChatImage,
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
  pendingUserImages: readonly ChatImage[]
  pendingUserContent: string
  streamText: string
  streamProgress: string
  streamProgressStatus: 'thinking' | 'completed' | 'failed'
  streamCompletedAt: string
  streamDurationMs: number | null
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
  pendingUserImages: [],
  pendingUserContent: '',
  streamText: '',
  streamProgress: '',
  streamProgressStatus: 'thinking',
  streamCompletedAt: '',
  streamDurationMs: null,
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
  private readonly deletedIds = new Set<string>()
  private openingId: string | null = null
  private state: ChatModelState = initialState
  private readonly listeners = new Set<ChatListener>()
  private readonly requestId: () => string
  private readonly pendingBackgroundRefresh = new Set<string>()
  private readonly backgroundStreams = new Set<ApiStreamTask>()
  private activeStream: ApiStreamTask | null = null
  private streamSucceeded = false
  private streamSequence = 0
  private streamRequestId = ''
  private streamRunId = ''
  private streamGeneration = 0
  private historyGeneration = 0
  private pendingImageSend: { signature: string; clientMessageId: string; idempotencyKey: string } | null = null
  private pendingCreate: { title: string; idempotencyKey: string } | null = null
  private createInFlight: Promise<ConversationSummary | null> | null = null

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

  async setFeedback(messageId: string, resolved: boolean): Promise<void> {
    const conversation = this.state.activeConversation
    const message = conversation?.messages.find(row => row.id === messageId)
    if (!conversation || message?.role !== 'assistant' || message.resolved === undefined) {
      throw new Error('这条回答暂不可评价')
    }
    if (message.resolved !== null) {
      if (message.resolved === resolved) return
      throw new Error('评价已确认，不能修改')
    }
    const auth = this.authProvider()
    const result = await this.client.setFeedback(conversation.id, messageId, resolved, { auth })
    if (result.fromFallback) {
      if (result.problemCode === 'FEEDBACK_ALREADY_SUBMITTED') {
        const latest = await this.client.get(conversation.id, { auth })
        const saved = latest.payload.messages.find(row => row.id === messageId)?.resolved
        const current = this.state.activeConversation
        if (!latest.fromFallback && typeof saved === 'boolean' && current?.id === conversation.id) {
          this.update({ activeConversation: { ...current, messages: current.messages.map(row =>
            row.id === messageId ? { ...row, resolved: saved } : row) } })
        }
        throw new Error('评价已确认，不能修改')
      }
      throw new Error('反馈未保存，请重试')
    }
    const current = this.state.activeConversation
    if (current?.id !== conversation.id) return
    this.update({ activeConversation: { ...current, messages: current.messages.map(row =>
      row.id === messageId ? { ...row, resolved: result.payload.resolved } : row) } })
  }

  subscribe(listener: ChatListener): () => void {
    this.listeners.add(listener)
    listener(this.state)
    return () => this.listeners.delete(listener)
  }

  async load(): Promise<void> {
    const viewGeneration = this.beginViewRequest()
    const historyGeneration = this.historyGeneration + 1
    this.historyGeneration = historyGeneration
    this.update({ phase: 'loading', errorCode: '', errorMessage: '', retryable: false })
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    const result = await this.client.list({ limit: 20 }, { auth })
    if (
      viewGeneration !== this.streamGeneration
      || historyGeneration !== this.historyGeneration
    ) return
    if (result.fromFallback) {
      this.apiFailure(result, '会话历史加载失败')
      return
    }
    const conversations = result.payload.items.filter(item => !this.deletedIds.has(item.id))
    this.update({
      phase: 'ready',
      conversations,
      nextCursor: result.payload.nextCursor,
      activeConversation: null,
      pendingUserImages: [],
      pendingUserContent: '',
      streamText: '',
      streamProgress: '',
      streamProgressStatus: 'thinking',
      streamCompletedAt: '',
      streamDurationMs: null,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    const first = conversations[0]
    if (first && viewGeneration === this.streamGeneration) await this.open(first.id)
  }

  async loadMore(): Promise<void> {
    if (!this.state.nextCursor) return
    const generation = this.historyGeneration + 1
    this.historyGeneration = generation
    const viewGeneration = this.streamGeneration
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
    if (generation !== this.historyGeneration) return
    if (result.fromFallback) {
      if (viewGeneration === this.streamGeneration) this.apiFailure(result, '更多会话加载失败')
      return
    }
    const byId = new Map(this.state.conversations.map((item) => [item.id, item]))
    result.payload.items.filter(item => !this.deletedIds.has(item.id)).forEach((item) => byId.set(item.id, item))
    this.update({
      conversations: [...byId.values()],
      nextCursor: result.payload.nextCursor,
      ...(viewGeneration === this.streamGeneration && this.state.phase !== 'sending'
        ? { phase: 'ready' as const, errorCode: '', errorMessage: '', retryable: false }
        : {}),
    })
  }

  async open(conversationId: string): Promise<void> {
    this.pendingBackgroundRefresh.delete(conversationId)
    const generation = this.beginViewRequest()
    this.openingId = conversationId
    this.update({ phase: 'loading', pendingUserImages: [], pendingUserContent: '', streamText: '', streamProgress: '', streamProgressStatus: 'thinking', streamCompletedAt: '', streamDurationMs: null, })
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
      this.openingId = null
      this.apiFailure(result, '会话内容加载失败')
      return
    }
    this.openingId = null
    if (this.deletedIds.has(conversationId)) return
    this.update({
      phase: 'ready',
      activeConversation: result.payload,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    if (this.pendingBackgroundRefresh.delete(conversationId)) {
      await this.refreshAfterStream(conversationId, false, generation)
    }
  }

  async remove(conversationId: string): Promise<string | null> {
    try {
      const result = await this.client.remove(conversationId, { auth: this.authProvider() })
      if (result.fromFallback) return result.problemCode === 'CHAT_CONVERSATION_BUSY'
        ? '鸡哥正在回复此会话，请等待回复结束后再删除。' : '删除失败，请稍后重试。'
      this.deletedIds.add(conversationId)
      const conversations = this.state.conversations.filter(item => item.id !== conversationId)
      if (this.openingId === conversationId || (!this.openingId && this.state.activeConversation?.id === conversationId)) {
        this.beginViewRequest()
        this.update({ ...initialState, phase: 'ready', conversations, nextCursor: this.state.nextCursor })
      } else if (this.state.activeConversation?.id === conversationId) {
        this.update({ ...initialState, phase: this.state.phase, conversations, nextCursor: this.state.nextCursor })
      } else {
        this.update({ conversations })
      }
      return null
    } catch {
      return '删除失败，请稍后重试。'
    }
  }

  create(title?: string): Promise<ConversationSummary | null> {
    if (this.createInFlight) return this.createInFlight
    const operation = this.createOnce(title)
    const tracked = operation.finally(() => {
      if (this.createInFlight === tracked) this.createInFlight = null
    })
    this.createInFlight = tracked
    return tracked
  }

  private async createOnce(title?: string): Promise<ConversationSummary | null> {
    const viewGeneration = this.beginViewRequest()
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
      if (viewGeneration === this.streamGeneration) this.apiFailure(result, '新建会话失败')
      return null
    }
    if (this.pendingCreate === pending) this.pendingCreate = null
    const conversations = [
      result.payload,
      ...this.state.conversations.filter((item) => item.id !== result.payload.id),
    ]
    this.update({ conversations })
    if (viewGeneration === this.streamGeneration) await this.open(result.payload.id)
    return result.payload
  }

  send(content: string, images: readonly ChatImage[] = [], onAccepted?: () => void): ApiStreamTask | null {
    if (this.state.phase === 'sending') return this.activeStream
    const conversation = this.state.activeConversation
    const normalized = content.trim()
    if (!conversation || (!normalized && !images.length)) {
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
    this.streamSucceeded = false
    this.streamSequence = 0
    this.streamRequestId = ''
    this.streamRunId = ''
    this.update({
      phase: 'sending',
      pendingUserContent: normalized,
      pendingUserImages: images,
      streamText: '',
      streamProgress: '',
      streamProgressStatus: 'thinking',
      streamCompletedAt: '',
      streamDurationMs: null,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    const signature = JSON.stringify([conversation.id, normalized, images.map(image => image.id)])
    const requestIdentity = images.length && this.pendingImageSend?.signature === signature
      ? this.pendingImageSend
      : { signature, clientMessageId: boundedRequestId(this.requestId(), 'client-message'),
          idempotencyKey: boundedRequestId(this.requestId(), 'idempotency') }
    if (images.length) this.pendingImageSend = requestIdentity
    const { clientMessageId, idempotencyKey } = requestIdentity
    let admissionSeen = false
    let endedDuringStart = false
    let task: ApiStreamTask | null = null
    const finishBackground = () => {
      if (!task || !this.backgroundStreams.delete(task)) return
      this.pendingBackgroundRefresh.add(conversation.id)
      if (this.state.activeConversation?.id === conversation.id
        && (this.state.phase === 'ready' || this.state.phase === 'blocked')) {
        this.pendingBackgroundRefresh.delete(conversation.id)
        void this.refreshAfterStream(conversation.id, false, this.streamGeneration)
      }
    }
    try {
      task = this.client.streamMessage(
        conversation.id,
        { content: normalized, clientMessageId, ...(images.length ? {imageIds: images.map(image => image.id)} : {}) },
        {
          auth,
          idempotencyKey,
          onEvent: (event) => {
            if (event.type === 'completed' || event.type === 'failed') {
              endedDuringStart = true
              finishBackground()
            }
            this.onStreamEvent(event, conversation.id, generation)
            if (generation === this.streamGeneration && !admissionSeen && event.type === 'started' && event.sequence === 1 && event.conversationId === conversation.id) {
              admissionSeen = true
              onAccepted?.()
            }
            if (this.state.phase !== 'sending') endedDuringStart = true
          },
          onFailure: (error) => {
            endedDuringStart = true
            finishBackground()
            this.onStreamFailure(error, conversation.id, generation)
          },
        },
      )
    } catch {
      this.onStreamFailure('CHAT_TRANSPORT_UNAVAILABLE', conversation.id, generation)
      return null
    }
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
    const activeStream = this.activeStream
    this.activeStream = null
    this.streamGeneration += 1
    this.historyGeneration += 1
    activeStream?.abort()
    for (const stream of this.backgroundStreams) stream.abort()
    this.backgroundStreams.clear()
    this.pendingBackgroundRefresh.clear()
    this.listeners.clear()
  }

  private beginViewRequest(): number {
    this.openingId = null
    this.streamSucceeded = false
    const activeStream = this.activeStream
    this.activeStream = null
    this.streamGeneration += 1
    if (activeStream) this.backgroundStreams.add(activeStream)
    return this.streamGeneration
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
    if (event.type === 'progress') {
      this.update({ streamProgress: Array.from(this.state.streamProgress + event.text).slice(0, 16000).join(''),
        streamProgressStatus: 'thinking' })
      return
    }
    if (event.type === 'delta') {
      this.update({ streamText: this.state.streamText + event.text, streamProgressStatus: 'completed' })
      return
    }
    if (event.type === 'completed') {
      this.streamSucceeded = true
      this.activeStream = null
      this.update({ streamText: event.text, streamProgressStatus: 'completed',
        streamCompletedAt: event.completedAt ?? '', streamDurationMs: event.durationMs ?? null })
      void this.refreshAfterStream(conversationId, false, generation)
      return
    }
    if (event.type === 'failed') {
      this.update({ streamCompletedAt: event.completedAt ?? '', streamDurationMs: event.durationMs ?? null })
      this.activeStream = null
      this.fail(event.errorCode, '本次回答未完成，用户消息已保留', event.retryable)
      void this.refreshAfterStream(conversationId, true, generation)
    }
  }

  private onStreamFailure(error: string, conversationId: string, generation: number): void {
    if (generation !== this.streamGeneration) return
    this.activeStream = null
    this.fail(error || 'CHAT_STREAM_FAILED', error === 'CHAT_ACCOUNT_BUSY'
      ? '鸡哥正在回复你的另一条消息，请等待回复结束后再发送。'
      : '回答连接中断，正在恢复服务端历史', true)
    void this.refreshAfterStream(conversationId, true, generation)
  }

  private async refreshAfterStream(
    conversationId: string,
    preserveFailure: boolean,
    generation: number,
  ): Promise<void> {
    if (generation !== this.streamGeneration || this.deletedIds.has(conversationId)) return
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
      pendingUserImages: [],
      pendingUserContent: '',
      streamText: '',
      streamProgress: '',
      streamProgressStatus: 'thinking',
      streamCompletedAt: '',
      streamDurationMs: null,
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
      ...(this.streamSucceeded ? {} : { streamText: '', streamProgressStatus: 'failed' as const }),
    })
  }

  private update(patch: Partial<ChatModelState>): void {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener(this.state))
  }
}
