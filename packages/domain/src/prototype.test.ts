import { describe, expect, it } from 'vitest'

import {
  isPrototypeChatStreamEvent,
  isPrototypeConversationResponse,
  isPrototypeSessionResponse,
  isPrototypeSimulationResponse,
  isPrototypeSnapshotResponse,
} from './prototype'

const requestId = 'request-123'

describe('prototype public response guards', () => {
  it('accepts public session, conversation, snapshot, simulation and stream values', () => {
    expect(isPrototypeSessionResponse({
      mode: 'prototype',
      sessionToken: 'a'.repeat(64),
      expiresAt: '2026-09-01T12:00:00.000Z',
      requestId,
    })).toBe(true)
    expect(isPrototypeConversationResponse({
      conversationId: 'conversation-1',
      title: '炸鸡队长对话',
      status: 'active',
      createdAt: '2026-09-01T12:00:00.000Z',
      updatedAt: '2026-09-01T12:00:00.000Z',
      messages: [],
      requestId,
    })).toBe(true)
    expect(isPrototypeSnapshotResponse({
      snapshotId: 'snapshot-1',
      provider: 'raiderio',
      sourceUrl: 'https://raider.io/characters/example/hero',
      sourceKey: 'raiderio:example',
      revision: 1,
      readiness: 'INCOMPLETE_FOR_SIMC',
      blockers: ['missing_gems'],
      snapshot: {},
      provenance: {},
      rawSha256: 'b'.repeat(64),
      fetchedAt: '2026-09-01T12:00:00.000Z',
      requestId,
    })).toBe(true)
    expect(isPrototypeSimulationResponse({
      jobId: 'job-1',
      snapshotId: 'snapshot-1',
      status: 'queued',
      scenarioHash: 'c'.repeat(64),
      compilerRevision: 'compiler-1',
      runtimeRevision: 'runtime-1',
      errorCode: null,
      createdAt: '2026-09-01T12:00:00.000Z',
      updatedAt: '2026-09-01T12:00:00.000Z',
      requestId,
    })).toBe(true)
    expect(isPrototypeChatStreamEvent({
      type: 'delta',
      requestId,
      conversationId: 'conversation-1',
      sequence: 1,
      text: 'hello',
    })).toBe(true)
  })

  it('rejects internal owner fields and malformed readiness or stream values', () => {
    const base = {
      snapshotId: 'snapshot-1',
      provider: 'raiderio',
      sourceUrl: 'https://raider.io/characters/example/hero',
      sourceKey: 'raiderio:example',
      revision: 1,
      readiness: 'READY_FOR_SIMC',
      blockers: [],
      snapshot: {},
      provenance: {},
      rawSha256: 'b'.repeat(64),
      fetchedAt: '2026-09-01T12:00:00.000Z',
      requestId,
    }
    expect(isPrototypeSnapshotResponse({ ...base, userId: 'private' })).toBe(false)
    expect(isPrototypeSnapshotResponse({ ...base, readiness: 'READY' })).toBe(false)
    expect(isPrototypeChatStreamEvent({
      type: 'delta',
      requestId,
      conversationId: 'conversation-1',
      sequence: 0,
      text: 'hello',
    })).toBe(false)
    expect(isPrototypeChatStreamEvent({
      type: 'completed',
      requestId,
      conversationId: 'conversation-1',
      sequence: 1,
      text: 'hello',
      ownerId: 'private',
    })).toBe(false)
  })
})
