export type ConversationStatus = 'active' | 'archived'
export type ChatMessageRole = 'user' | 'assistant'

export interface ConversationSummary {
  id: string
  title: string
  status: ConversationStatus
  createdAt: string
  updatedAt: string
}

export interface ChatProgress {
  text: string
  status: 'completed' | 'failed'
  completedAt: string
  durationMs: number | null
}

export interface ChatMessage {
  // Present only when the server has a completed, feedback-eligible answer.
  resolved?: boolean | null
  progress?: ChatProgress
  id: string
  role: ChatMessageRole
  content: string
  createdAt: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: readonly ChatMessage[]
}

export interface ConversationPage {
  items: readonly ConversationSummary[]
  nextCursor: string | null
}

interface ChatEventBase {
  requestId: string
  conversationId: string
  runId: string
  sequence: number
}

export type ChatEventEnvelope =
  | (ChatEventBase & { type: 'started' })
  | (ChatEventBase & { type: 'delta' | 'progress'; text: string })
  | (ChatEventBase & { type: 'completed'; text: string; completedAt?: string; durationMs?: number })
  | (ChatEventBase & { type: 'failed'; errorCode: string; retryable: boolean; completedAt?: string; durationMs?: number })


function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value)
  return actual.length === keys.length && actual.every((key) => keys.includes(key))
}

function nonEmptyString(value: unknown, maximum = 4096): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= maximum
}

function boundedString(value: unknown, maximum: number): value is string {
  return typeof value === 'string' && value.length <= maximum
}

function isoDate(value: unknown): value is string {
  return nonEmptyString(value, 128) && Number.isFinite(Date.parse(value))
}

function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
}

function isConversationSummaryRecord(value: unknown): value is ConversationSummary {
  if (!record(value) || !exactKeys(value, ['id', 'title', 'status', 'createdAt', 'updatedAt'])) return false
  return nonEmptyString(value['id'], 128)
    && boundedString(value['title'], 256)
    && (value['status'] === 'active' || value['status'] === 'archived')
    && isoDate(value['createdAt'])
    && isoDate(value['updatedAt'])
}

function nonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function boundedCodePoints(value: unknown, maximum: number): value is string {
  return typeof value === 'string' && value.length <= maximum * 2 && Array.from(value).length <= maximum
}

function isProgress(value: unknown): value is ChatProgress {
  return record(value) && exactKeys(value, ['text', 'status', 'completedAt', 'durationMs'])
    && boundedCodePoints(value['text'], 16000)
    && (value['status'] === 'completed' || value['status'] === 'failed')
    && isoDate(value['completedAt'])
    && (value['durationMs'] === null || nonnegativeInteger(value['durationMs']))
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!record(value) || !exactKeys(value, ['id', 'role', 'content', 'createdAt',
    ...('resolved' in value ? ['resolved'] : []),
    ...('progress' in value ? ['progress'] : [])])) return false
  if ('resolved' in value && (value['role'] !== 'assistant'
    || (value['resolved'] !== null && typeof value['resolved'] !== 'boolean'))) return false
  if ('progress' in value && (value['role'] !== 'assistant' || !isProgress(value['progress']))) return false
  return nonEmptyString(value['id'], 128)
    && (value['role'] === 'user' || value['role'] === 'assistant')
    && (nonEmptyString(value['content'], 100000)
      || (value['content'] === '' && isProgress(value['progress']) && value['progress'].status === 'failed'))
    && isoDate(value['createdAt'])
}

export function isConversationPage(value: unknown): value is ConversationPage {
  if (!record(value) || !exactKeys(value, ['items', 'nextCursor'])) return false
  return Array.isArray(value['items'])
    && value['items'].length <= 50
    && value['items'].every(isConversationSummaryRecord)
    && (value['nextCursor'] === null || nonEmptyString(value['nextCursor'], 1024))
}

export function isConversationDetail(value: unknown): value is ConversationDetail {
  if (!record(value) || !exactKeys(
    value,
    ['id', 'title', 'status', 'createdAt', 'updatedAt', 'messages'],
  )) return false
  return isConversationSummaryRecord({
    id: value['id'],
    title: value['title'],
    status: value['status'],
    createdAt: value['createdAt'],
    updatedAt: value['updatedAt'],
  })
    && Array.isArray(value['messages'])
    && value['messages'].every(isChatMessage)
}

export function isConversationSummary(value: unknown): value is ConversationSummary {
  return isConversationSummaryRecord(value)
}

export function isChatEventEnvelope(value: unknown): value is ChatEventEnvelope {
  if (!record(value)) return false
  const baseValid = nonEmptyString(value['requestId'], 128)
    && nonEmptyString(value['conversationId'], 128)
    && nonEmptyString(value['runId'], 128)
    && positiveInteger(value['sequence'])
  if (!baseValid) return false
  if (value['type'] === 'started') {
    return exactKeys(value, ['type', 'requestId', 'conversationId', 'runId', 'sequence'])
  }
  const timingKeys = ['completedAt', 'durationMs'].filter((key) => key in value)
  if (timingKeys.length && (timingKeys.length !== 2
    || !['completed', 'failed'].includes(String(value['type']))
    || !isoDate(value['completedAt']) || !nonnegativeInteger(value['durationMs']))) return false
  if (value['type'] === 'delta' || value['type'] === 'progress' || value['type'] === 'completed') {
    return exactKeys(value, ['type', 'requestId', 'conversationId', 'runId', 'sequence', 'text', ...timingKeys])
      && (value['type'] === 'progress'
        ? boundedCodePoints(value['text'], 8000) && value['text'].length > 0
        : nonEmptyString(value['text'], 8000))
  }
  return value['type'] === 'failed'
    && exactKeys(
      value,
      ['type', 'requestId', 'conversationId', 'runId', 'sequence', 'errorCode', 'retryable', ...timingKeys],
    )
    && nonEmptyString(value['errorCode'], 128)
    && typeof value['retryable'] === 'boolean'
}
