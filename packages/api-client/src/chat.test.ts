import { describe, expect, it, vi } from 'vitest'

import { createChatClient } from './chat'
import type {
  ApiResult,
  ApiStreamTask,
  ApiTransport,
  RequestOptions,
  SseStreamRequestOptions,
} from './transport'


class RecordingTransport implements ApiTransport {
  readonly requests: Array<{ path: string; options: RequestOptions<unknown> }> = []
  readonly streams: Array<{ path: string; options: SseStreamRequestOptions<unknown> }> = []

  async request<T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>> {
    this.requests.push({ path, options: options as RequestOptions<unknown> })
    return {
      payload: options.fallback(),
      fromFallback: false,
      error: '',
      httpStatus: 200,
    }
  }

  requestSse<T>(path: string, options: SseStreamRequestOptions<T>): ApiStreamTask {
    this.streams.push({ path, options: options as SseStreamRequestOptions<unknown> })
    return { abort() {} }
  }
}


describe('formal Chat client', () => {
  it('uses the isolated candidate prefix for every formal Chat route', async () => {
    vi.stubGlobal('__WOW_API_V2_PREFIX__', '/api/v2-candidate')
    try {
      const transport = new RecordingTransport()
      const client = createChatClient(transport)
      const auth = { kind: 'mini' as const, accessToken: 'mini-token' }

      await client.list({}, { auth })
      await client.create({}, { auth, idempotencyKey: 'create-request-one' })

      expect(transport.requests.map((call) => call.path)).toEqual([
        '/api/v2-candidate/chat/conversations',
        '/api/v2-candidate/chat/conversations',
      ])
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('uses only formal paths and delegates Mini credentials to the transport', async () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)
    const auth = { kind: 'mini' as const, accessToken: 'mini-token' }

    await client.list({ limit: 20 }, { auth })
    await client.create(
      { title: '跨端' },
      { auth, idempotencyKey: 'create-request-one' },
    )
    await client.get('conversation/one', { auth })

    expect(transport.requests.map((call) => call.path)).toEqual([
      '/api/v2/chat/conversations?limit=20',
      '/api/v2/chat/conversations',
      '/api/v2/chat/conversations/conversation%2Fone?includeProgress=true',
    ])
    for (const call of transport.requests) {
      expect(call.path).not.toContain('/prototype/')
      expect(call.options.auth).toEqual(auth)
      expect(call.options.credentials).toBeUndefined()
      expect(call.options.baseUrl).toBeUndefined()
      expect(call.options.header?.['Authorization']).toBeUndefined()
    }
    expect(transport.requests[1]?.options.header).toEqual({
      'Idempotency-Key': 'create-request-one',
    })
  })

  it('delegates Web Cookie and CSRF credentials to the transport', async () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)
    const auth = { kind: 'web' as const, csrfToken: 'web-csrf' }

    await client.list({}, { auth })
    await client.get('conversation-one', { auth })
    await client.create(
      { title: 'Web 跨端' },
      { auth, idempotencyKey: 'web-create-request-one' },
    )

    for (const [index, call] of transport.requests.entries()) {
      expect(call.options.auth).toEqual(auth)
      expect(call.options.credentials).toBeUndefined()
      expect(call.options.baseUrl).toBeUndefined()
      expect(call.options.header).toEqual(index === 2
        ? { 'Idempotency-Key': 'web-create-request-one' }
        : undefined)
      expect(call.options.header?.['Authorization']).toBeUndefined()
      expect(call.options.header?.['X-CSRF-Token']).toBeUndefined()
    }
  })

  it('rejects an invalid conversation creation idempotency key before transport', () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)

    expect(() => client.create(
      { title: '不会发送' },
      {
        auth: { kind: 'mini', accessToken: 'mini-token' },
        idempotencyKey: 'contains whitespace',
      },
    )).toThrow('idempotency key is invalid')
    expect(transport.requests).toEqual([])
  })

  it('streams formal SSE with auth context and validates events', () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)
    const failures: string[] = []

    client.streamMessage(
      'conversation-one',
      { content: '问题', clientMessageId: 'client-one' },
      {
        auth: { kind: 'web', csrfToken: 'web-csrf' },
        idempotencyKey: 'request-one',
        onEvent: () => {},
        onFailure: (error) => failures.push(error),
      },
    )

    const stream = transport.streams[0]
    expect(stream?.path).toBe('/api/v2/chat/conversations/conversation-one/messages/stream?includeProgress=true')
    expect(stream?.options).toMatchObject({
      method: 'POST',
      data: { content: '问题', clientMessageId: 'client-one' },
      auth: { kind: 'web', csrfToken: 'web-csrf' },
      header: {
        'Idempotency-Key': 'request-one',
      },
      timeoutMs: 510000,
    })
    expect(failures).toEqual([])
  })

  it('rejects malformed stream envelopes before they reach the caller', () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)
    const events: unknown[] = []
    const failures: string[] = []

    client.streamMessage(
      'conversation-one',
      { content: '问题', clientMessageId: 'client-one' },
      {
        auth: { kind: 'mini', accessToken: 'mini-token' },
        idempotencyKey: 'request-one',
        onEvent: (event) => events.push(event),
        onFailure: (error) => failures.push(error),
      },
    )
    const stream = transport.streams[0]
    expect(stream?.options).toMatchObject({
      auth: { kind: 'mini', accessToken: 'mini-token' },
      header: {
        'Idempotency-Key': 'request-one',
      },
    })
    stream?.options.onEvent({
      type: 'started',
      requestId: 'request-one',
      conversationId: 'conversation-one',
      runId: 'run-one',
      sequence: 1,
    })
    expect(() => stream?.options.onEvent({
      type: 'delta',
      requestId: 'request-one',
      conversationId: 'conversation-one',
      runId: 'run-one',
      sequence: 0,
      text: 'bad',
    })).toThrow('invalid chat stream event')

    expect(events).toHaveLength(1)
    expect(failures).toEqual(['invalid chat stream event'])
  })

  it('fails closed when a successful transport ends before a Chat terminal event', () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)
    const failures: string[] = []

    client.streamMessage(
      'conversation-one',
      { content: '问题', clientMessageId: 'client-one' },
      {
        auth: { kind: 'mini', accessToken: 'mini-token' },
        idempotencyKey: 'request-one',
        onEvent: () => {},
        onFailure: (error) => failures.push(error),
      },
    )
    const stream = transport.streams[0]
    stream?.options.onEvent({
      type: 'started',
      requestId: 'request-one',
      conversationId: 'conversation-one',
      runId: 'run-one',
      sequence: 1,
    })
    stream?.options.onEnd?.()

    expect(failures).toEqual(['chat stream ended before a terminal event'])
  })

  it.each(['completed', 'failed'] as const)(
    'accepts a natural transport end after a %s Chat event',
    (terminalType) => {
      const transport = new RecordingTransport()
      const client = createChatClient(transport)
      const events: unknown[] = []
      const failures: string[] = []

      client.streamMessage(
        'conversation-one',
        { content: '问题', clientMessageId: 'client-one' },
        {
          auth: { kind: 'web', csrfToken: 'web-csrf' },
          idempotencyKey: 'request-one',
          onEvent: (event) => events.push(event),
          onFailure: (error) => failures.push(error),
        },
      )
      const stream = transport.streams[0]
      const base = {
        type: terminalType,
        requestId: 'request-one',
        conversationId: 'conversation-one',
        runId: 'run-one',
        sequence: 1,
      }
      stream?.options.onEvent(terminalType === 'completed'
        ? { ...base, text: '回答' }
        : { ...base, errorCode: 'CODEX_EXECUTION_FAILED', retryable: true })
      stream?.options.onEnd?.()

      expect(events).toHaveLength(1)
      expect(failures).toEqual([])
    },
  )
})
