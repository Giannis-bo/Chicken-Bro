export type PrototypeReadiness =
  | 'INVALID_LINK'
  | 'CHARACTER_NOT_FOUND'
  | 'ACCESS_RESTRICTED'
  | 'SNAPSHOT_UNAVAILABLE'
  | 'INCOMPLETE_FOR_SIMC'
  | 'READY_FOR_SIMC'

export interface PrototypeSessionResponse {
  mode: 'prototype'
  sessionToken: string
  expiresAt: string
  requestId: string
}

export interface PrototypeMessage {
  messageId: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
}

export interface PrototypeConversationResponse {
  conversationId: string
  title: string
  status: 'active' | 'archived'
  createdAt: string
  updatedAt: string
  messages: readonly PrototypeMessage[]
  requestId: string
}

export interface PrototypeSnapshotResponse {
  snapshotId: string
  provider: 'raiderio' | 'warcraftlogs'
  sourceUrl: string
  sourceKey: string
  revision: number
  readiness: PrototypeReadiness
  blockers: readonly string[]
  snapshot: Readonly<Record<string, unknown>>
  provenance: Readonly<Record<string, unknown>>
  rawSha256: string
  fetchedAt: string
  requestId: string
}

export interface PrototypeSimulationMetric {
  name: string
  value: number
}

export interface PrototypeSimulationResult {
  profileSha256: string
  metric: PrototypeSimulationMetric
  compilerRevision: string
  runtimeRevision: string
  provenance: Readonly<Record<string, unknown>>
  createdAt: string
}

export interface PrototypeSimulationResponse {
  jobId: string
  snapshotId: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  scenarioHash: string
  compilerRevision: string
  runtimeRevision: string
  errorCode: string | null
  createdAt: string
  updatedAt: string
  result?: PrototypeSimulationResult
  requestId: string
}

export type PrototypeChatStreamEvent =
  | {
      type: 'started'
      requestId: string
      conversationId: string
      sequence: number
    }
  | {
      type: 'delta'
      requestId: string
      conversationId: string
      sequence: number
      text: string
    }
  | {
      type: 'completed'
      requestId: string
      conversationId: string
      sequence: number
      text: string
    }
  | {
      type: 'failed'
      requestId: string
      conversationId: string
      sequence: number
      errorCode: string
      retryable: boolean
    }

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function noPrivateOwnerKey(value: Record<string, unknown>): boolean {
  return !('userId' in value) && !('user_id' in value) && !('ownerId' in value) && !('owner_id' in value)
}

function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
}

export function isPrototypeSessionResponse(value: unknown): value is PrototypeSessionResponse {
  return record(value)
    && noPrivateOwnerKey(value)
    && value['mode'] === 'prototype'
    && nonEmptyString(value['sessionToken'])
    && nonEmptyString(value['expiresAt'])
    && nonEmptyString(value['requestId'])
}

export function isPrototypeConversationResponse(value: unknown): value is PrototypeConversationResponse {
  return record(value)
    && noPrivateOwnerKey(value)
    && nonEmptyString(value['conversationId'])
    && nonEmptyString(value['title'])
    && (value['status'] === 'active' || value['status'] === 'archived')
    && nonEmptyString(value['createdAt'])
    && nonEmptyString(value['updatedAt'])
    && Array.isArray(value['messages'])
    && value['messages'].every((message) => (
      record(message)
      && noPrivateOwnerKey(message)
      && nonEmptyString(message['messageId'])
      && (message['role'] === 'user' || message['role'] === 'assistant')
      && typeof message['content'] === 'string'
      && nonEmptyString(message['createdAt'])
    ))
    && nonEmptyString(value['requestId'])
}

export function isPrototypeSnapshotResponse(value: unknown): value is PrototypeSnapshotResponse {
  return record(value)
    && noPrivateOwnerKey(value)
    && nonEmptyString(value['snapshotId'])
    && (value['provider'] === 'raiderio' || value['provider'] === 'warcraftlogs')
    && nonEmptyString(value['sourceUrl'])
    && nonEmptyString(value['sourceKey'])
    && positiveInteger(value['revision'])
    && typeof value['readiness'] === 'string'
    && ['INVALID_LINK', 'CHARACTER_NOT_FOUND', 'ACCESS_RESTRICTED', 'SNAPSHOT_UNAVAILABLE', 'INCOMPLETE_FOR_SIMC', 'READY_FOR_SIMC'].includes(value['readiness'])
    && Array.isArray(value['blockers'])
    && value['blockers'].every(nonEmptyString)
    && record(value['snapshot'])
    && record(value['provenance'])
    && /^[0-9a-f]{64}$/u.test(String(value['rawSha256']))
    && nonEmptyString(value['fetchedAt'])
    && nonEmptyString(value['requestId'])
}

export function isPrototypeSimulationResponse(value: unknown): value is PrototypeSimulationResponse {
  return record(value)
    && noPrivateOwnerKey(value)
    && nonEmptyString(value['jobId'])
    && nonEmptyString(value['snapshotId'])
    && ['queued', 'running', 'succeeded', 'failed', 'cancelled'].includes(String(value['status']))
    && nonEmptyString(value['scenarioHash'])
    && nonEmptyString(value['compilerRevision'])
    && nonEmptyString(value['runtimeRevision'])
    && (value['errorCode'] === null || nonEmptyString(value['errorCode']))
    && nonEmptyString(value['createdAt'])
    && nonEmptyString(value['updatedAt'])
    && nonEmptyString(value['requestId'])
    && (value['result'] === undefined || record(value['result']))
}

export function isPrototypeChatStreamEvent(value: unknown): value is PrototypeChatStreamEvent {
  if (!record(value) || !noPrivateOwnerKey(value)) return false
  if (!nonEmptyString(value['requestId']) || !nonEmptyString(value['conversationId']) || !positiveInteger(value['sequence'])) return false
  if (value['type'] === 'started') return true
  if (value['type'] === 'delta' || value['type'] === 'completed') return typeof value['text'] === 'string'
  return value['type'] === 'failed' && nonEmptyString(value['errorCode']) && typeof value['retryable'] === 'boolean'
}
