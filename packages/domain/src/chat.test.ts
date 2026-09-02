import { describe, expect, it } from 'vitest'

import {
  isChatEventEnvelope,
  isConversationDetail,
  isConversationPage,
} from './chat'


const conversationId = '00000000-0000-4000-8000-000000000301'
const messageId = '00000000-0000-4000-8000-000000000302'
const runId = '00000000-0000-4000-8000-000000000303'
const timestamp = '2026-09-03T09:00:00+00:00'


describe('formal Chat domain guards', () => {
  it('accepts the exact owner-free conversation page and detail contracts', () => {
    expect(isConversationPage({
      items: [{
        id: conversationId,
        title: '跨端',
        status: 'active',
        createdAt: timestamp,
        updatedAt: timestamp,
      }],
      nextCursor: null,
    })).toBe(true)
    expect(isConversationDetail({
      id: conversationId,
      title: '跨端',
      status: 'active',
      createdAt: timestamp,
      updatedAt: timestamp,
      messages: [{
        id: messageId,
        role: 'user',
        content: '问题',
        createdAt: timestamp,
      }],
    })).toBe(true)
  })

  it('rejects owner fields, missing required fields, and unknown payload expansion', () => {
    const summary = {
      id: conversationId,
      title: '跨端',
      status: 'active',
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    expect(isConversationPage({
      items: Array.from({ length: 51 }, () => summary),
      nextCursor: null,
    })).toBe(false)
    expect(isConversationPage({
      items: [{ id: conversationId, userId: conversationId }],
      nextCursor: null,
    })).toBe(false)
    expect(isConversationPage({
      items: [{
        id: conversationId,
        title: '跨端',
        status: 'active',
        createdAt: timestamp,
        updatedAt: timestamp,
        runtimeRevision: 'private-expansion',
      }],
      nextCursor: null,
    })).toBe(false)
    expect(isConversationDetail({
      id: conversationId,
      title: '跨端',
      status: 'active',
      createdAt: timestamp,
      updatedAt: timestamp,
      messages: [{
        id: messageId,
        role: 'assistant',
        content: '回答',
        createdAt: timestamp,
        owner_id: conversationId,
      }],
    })).toBe(false)
  })

  it('accepts only exact monotonic-capable public SSE envelopes', () => {
    const base = {
      requestId: '00000000-0000-4000-8000-000000000304',
      conversationId,
      runId,
    }
    expect(isChatEventEnvelope({ ...base, type: 'started', sequence: 1 })).toBe(true)
    expect(isChatEventEnvelope({ ...base, type: 'delta', sequence: 2, text: '回' })).toBe(true)
    expect(isChatEventEnvelope({ ...base, type: 'completed', sequence: 3, text: '回答' })).toBe(true)
    expect(isChatEventEnvelope({
      ...base,
      type: 'failed',
      sequence: 2,
      errorCode: 'CODEX_TIMEOUT',
      retryable: true,
    })).toBe(true)

    expect(isChatEventEnvelope({ ...base, type: 'delta', sequence: 0, text: 'bad' })).toBe(false)
    expect(isChatEventEnvelope({ ...base, type: 'delta', sequence: 2, text: '' })).toBe(false)
    expect(isChatEventEnvelope({ ...base, type: 'started', sequence: 1, user_id: conversationId })).toBe(false)
    expect(isChatEventEnvelope({ ...base, type: 'completed', sequence: 2 })).toBe(false)
  })
})
