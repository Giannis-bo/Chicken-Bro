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
      await client.create({}, { auth })

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
    await client.create({ title: '跨端' }, { auth })
    await client.get('conversation/one', { auth })

    expect(transport.requests.map((call) => call.path)).toEqual([
      '/api/v2/chat/conversations?limit=20',
      '/api/v2/chat/conversations',
      '/api/v2/chat/conversations/conversation%2Fone',
    ])
    for (const call of transport.requests) {
      expect(call.path).not.toContain('/prototype/')
      expect(call.options.auth).toEqual(auth)
      expect(call.options.credentials).toBeUndefined()
      expect(call.options.baseUrl).toBeUndefined()
      expect(call.options.header?.['Authorization']).toBeUndefined()
    }
  })

  it('delegates Web Cookie and CSRF credentials to the transport', async () => {
    const transport = new RecordingTransport()
    const client = createChatClient(transport)
    const auth = { kind: 'web' as const, csrfToken: 'web-csrf' }

    await client.list({}, { auth })
    await client.get('conversation-one', { auth })
    await client.create({ title: 'Web 跨端' }, { auth })

    for (const call of transport.requests) {
      expect(call.options.auth).toEqual(auth)
      expect(call.options.credentials).toBeUndefined()
      expect(call.options.baseUrl).toBeUndefined()
      expect(call.options.header).toBeUndefined()
      expect(call.options.header?.['Authorization']).toBeUndefined()
      expect(call.options.header?.['X-CSRF-Token']).toBeUndefined()
    }
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
    expect(stream?.path).toBe('/api/v2/chat/conversations/conversation-one/messages/stream')
    expect(stream?.options).toMatchObject({
      method: 'POST',
      data: { content: '问题', clientMessageId: 'client-one' },
      auth: { kind: 'web', csrfToken: 'web-csrf' },
      header: {
        'Idempotency-Key': 'request-one',
      },
      timeoutMs: 180000,
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
    stream?.options.onEvent({
      type: 'delta',
      requestId: 'request-one',
      conversationId: 'conversation-one',
      runId: 'run-one',
      sequence: 0,
      text: 'bad',
    })

    expect(events).toHaveLength(1)
    expect(failures).toEqual(['invalid chat stream event'])
  })
})
