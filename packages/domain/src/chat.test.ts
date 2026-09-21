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

it('accepts only nullable boolean resolution feedback on assistant replies', () => {
  const detail = (resolved: unknown, role = 'assistant') => ({
    id: conversationId, title: '反馈', status: 'active', createdAt: timestamp, updatedAt: timestamp,
    messages: [{ id: messageId, role, content: '回答', createdAt: timestamp, resolved }],
  })
  for (const value of [null, true, false]) expect(isConversationDetail(detail(value))).toBe(true)
  for (const value of ['false', 0, {}, undefined]) expect(isConversationDetail(detail(value))).toBe(false)
  expect(isConversationDetail(detail(false, 'user'))).toBe(false)
})


describe('formal Chat domain guards', () => {
  it('accepts persisted game identity and rejects unknown games', () => {
    const summary = {id: conversationId, title: 'BD', status: 'active', createdAt: timestamp, updatedAt: timestamp}
    for (const game of ['wow', 'poe2']) {
      expect(isConversationPage({items: [{...summary, game}], nextCursor: null})).toBe(true)
      expect(isConversationDetail({...summary, game, messages: []})).toBe(true)
    }
    expect(isConversationPage({items: [{...summary, game: 'poe1'}], nextCursor: null})).toBe(false)
  })
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

  it('accepts the complete persisted conversation title range', () => {
    const summary = {
      id: conversationId,
      status: 'active',
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    expect(isConversationPage({
      items: [{ ...summary, title: '' }],
      nextCursor: null,
    })).toBe(true)
    expect(isConversationPage({
      items: [{ ...summary, title: '长'.repeat(256) }],
      nextCursor: null,
    })).toBe(true)
    expect(isConversationPage({
      items: [{ ...summary, title: '长'.repeat(257) }],
      nextCursor: null,
    })).toBe(false)
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

it('accepts bounded public progress and terminal timing without accepting raw reasoning fields', () => {
  const base = { requestId: 'req', conversationId, runId, sequence: 2 }
  expect(isChatEventEnvelope({ ...base, type: 'progress', text: '核对日志' })).toBe(true)
  expect(isChatEventEnvelope({ ...base, type: 'progress', text: '核对日志', reasoning: 'private' })).toBe(false)
  const terminal = { ...base, type: 'completed', text: '结论', completedAt: timestamp, durationMs: 18000 }
  expect(isChatEventEnvelope(terminal)).toBe(true)
  expect(isChatEventEnvelope({ ...terminal, durationMs: -1 })).toBe(false)
  expect(isChatEventEnvelope({ ...terminal, durationMs: Infinity })).toBe(false)
})

it('accepts emoji progress using the same Unicode character limit as PostgreSQL', () => {
  expect(isChatEventEnvelope({ requestId: 'req', conversationId, runId, sequence: 2,
    type: 'progress', text: '🐔'.repeat(8000) })).toBe(true)
  expect(isConversationDetail({ id: conversationId, title: '日志', status: 'active',
    createdAt: timestamp, updatedAt: timestamp, messages: [{ id: messageId,
      role: 'assistant', content: '结论', createdAt: timestamp,
      progress: { text: '🐔'.repeat(16000), status: 'completed', completedAt: timestamp, durationMs: 0 },
    }] })).toBe(true)
})

it('accepts image-only user history and rejects malformed or ownership-bearing image metadata', () => {
  const image = {id: 'image-one', mimeType: 'image/png', width: 2, height: 2}
  const detail = (images: unknown, role = 'user') => ({
    id: conversationId, title: '图片', status: 'active', createdAt: timestamp, updatedAt: timestamp,
    messages: [{id: messageId, role, content: '', createdAt: timestamp, images}],
  })
  expect(isConversationDetail(detail([image]))).toBe(true)
  for (const images of [[], [image, image], [{...image, owner: 'someone'}], [{...image, width: 9000}], [{...image, mimeType: 'image/svg+xml'}]]) {
    expect(isConversationDetail(detail(images))).toBe(false)
  }
  expect(isConversationDetail(detail([image], 'assistant'))).toBe(false)
})
