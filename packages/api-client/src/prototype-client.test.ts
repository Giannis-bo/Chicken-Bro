import { describe, expect, it } from 'vitest'

import type { ApiResult, ApiTransport, SseStreamRequestOptions } from './transport'
import { createPrototypeWebClient, PROTOTYPE_SESSION_STORAGE_KEY } from './prototype-client'

class MemoryStorage {
  private readonly values = new Map<string, string>()

  getItem(key: string): string | null {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value)
  }

  removeItem(key: string): void {
    this.values.delete(key)
  }
}

function result<T>(payload: T, status = 200): ApiResult<T> {
  return { payload, fromFallback: false, error: '', httpStatus: status }
}

function transportFor(
  request: (path: string, options: Record<string, unknown>) => ApiResult<unknown>,
  requestSse?: <T>(path: string, options: SseStreamRequestOptions<T>) => { abort(): void },
): ApiTransport {
  return {
    request: async <T>(path: string, options: Record<string, unknown>) => request(path, options) as ApiResult<T>,
    requestEndpoint: async <T>() => result<T>(undefined as T),
    ...(requestSse ? { requestSse } : {}),
  } as unknown as ApiTransport
}

describe('prototype web client', () => {
  it('keeps an opaque session in its own tab storage and omits formal credentials', async () => {
    const storage = new MemoryStorage()
    const calls: Array<{ path: string; options: Record<string, unknown> }> = []
    const transport = transportFor((path, options) => {
      calls.push({ path, options })
      if (path.endsWith('/sessions')) {
        return result({ mode: 'prototype', sessionToken: 'a'.repeat(64), expiresAt: '2026-09-01T12:00:00.000Z', requestId: 'request-1' })
      }
      return result({
        conversationId: 'conversation-1',
        title: '炸鸡队长对话',
        status: 'active',
        createdAt: '2026-09-01T12:00:00.000Z',
        updatedAt: '2026-09-01T12:00:00.000Z',
        messages: [],
        requestId: 'request-2',
      })
    })
    const client = createPrototypeWebClient(transport, storage)

    await client.createSession()
    await client.createConversation()

    expect(storage.getItem(PROTOTYPE_SESSION_STORAGE_KEY)).toBe('a'.repeat(64))
    expect(calls[1]).toMatchObject({
      path: '/api/v2/prototype/conversations',
      options: {
        auth: false,
        baseUrl: 'web-auth',
        credentials: 'omit',
        attachAnalyticsHeaders: false,
        header: { 'X-Prototype-Session': 'a'.repeat(64) },
      },
    })
    expect((calls[1]!.options['header'] as Record<string, string>)['Authorization']).toBeUndefined()
  })

  it('forwards only validated stream events and reports malformed events', () => {
    const storage = new MemoryStorage()
    storage.setItem(PROTOTYPE_SESSION_STORAGE_KEY, 'a'.repeat(64))
    const events: unknown[] = []
    const failures: string[] = []
    const transport = transportFor(
      () => result({}),
      <T>(_path: string, options: SseStreamRequestOptions<T>) => {
        options.onEvent({ type: 'delta', requestId: 'request-1', conversationId: 'conversation-1', sequence: 1, text: 'ok' } as T)
        options.onEvent({ type: 'delta', requestId: 'request-1', conversationId: 'conversation-1', sequence: 0, text: 'bad' } as T)
        return { abort() {} }
      },
    )
    const client = createPrototypeWebClient(transport, storage)

    client.streamMessage('conversation-1', 'hello', 'message-1', 'idempotency-1', {
      onEvent: (event) => events.push(event),
      onFailure: (failure) => failures.push(failure),
    })

    expect(events).toHaveLength(1)
    expect(failures).toEqual(['invalid prototype stream event'])
  })

  it('maps the transport timeout to the stable prototype error code', () => {
    const failures: string[] = []
    const transport = transportFor(
      () => result({}),
      <T>(_path: string, options: SseStreamRequestOptions<T>) => {
        options.onFailure('request timed out')
        return { abort() {} }
      },
    )
    const client = createPrototypeWebClient(transport, new MemoryStorage())

    client.streamMessage('conversation-1', 'hello', 'message-1', 'idempotency-1', {
      onEvent: () => {},
      onFailure: (failure) => failures.push(failure),
    })

    expect(failures).toEqual(['CODEX_TIMEOUT'])
  })

  it('uses the same web origin base for the prototype SSE endpoint', () => {
    let requestOptions: SseStreamRequestOptions<unknown> | undefined
    const transport = transportFor(
      () => result({}),
      <T>(_path: string, options: SseStreamRequestOptions<T>) => {
        requestOptions = options as SseStreamRequestOptions<unknown>
        return { abort() {} }
      },
    )
    const client = createPrototypeWebClient(transport, new MemoryStorage())

    client.streamMessage('conversation-1', 'hello', 'message-1', 'idempotency-1', {
      onEvent: () => {},
      onFailure: () => {},
    })

    expect(requestOptions?.baseUrl).toBe('web-auth')
    expect(requestOptions?.timeoutMs).toBe(180000)
  })
})
