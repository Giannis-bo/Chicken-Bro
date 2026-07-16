import Taro from '@tarojs/taro'

import { storageKey } from '@wow-mini/domain'

import { isRecord } from './guards'
import { taroStorage, type StorageAdapter } from './storage'
import type { ApiTransport } from './transport'

const maxQueueSize = 200
const maxBatchSize = 20

export interface AnalyticsEvent {
  eventId: string
  eventName: string
  occurredAt: string
  page: string
  properties: Readonly<Record<string, unknown>>
}

function parseQueue(storage: StorageAdapter): readonly AnalyticsEvent[] {
  const stored = storage.get<unknown>(storageKey('analytics.queue'))
  if (Array.isArray(stored)) return stored.filter(isRecord) as unknown as readonly AnalyticsEvent[]
  if (typeof stored !== 'string' || !stored) return []
  try {
    const parsed: unknown = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed.filter(isRecord) as unknown as readonly AnalyticsEvent[] : []
  } catch {
    return []
  }
}

function currentRoute(): string {
  const pages = Taro.getCurrentPages()
  return pages[pages.length - 1]?.route ?? ''
}

export class AnalyticsEventsClient {
  private flushing = false

  constructor(
    private readonly transport: ApiTransport,
    private readonly storage: StorageAdapter = taroStorage,
  ) {}

  private save(queue: readonly AnalyticsEvent[]): void {
    this.storage.set(storageKey('analytics.queue'), JSON.stringify(queue.slice(-maxQueueSize)))
  }

  async flush(): Promise<boolean> {
    if (this.flushing) return false
    const queue = parseQueue(this.storage)
    if (!queue.length) return true
    const batch = queue.slice(0, maxBatchSize)
    this.flushing = true
    try {
      const result = await this.transport.request('/api/analytics/events', {
        method: 'POST',
        data: { platform: 'miniprogram', events: batch },
        timeoutMs: 15000,
        fallback: () => ({ accepted: false }),
        validate: (value) => isRecord(value),
      })
      if (!result.fromFallback) this.save(queue.slice(batch.length))
      return !result.fromFallback
    } finally {
      this.flushing = false
    }
  }

  track(
    eventName: string,
    properties: Readonly<Record<string, unknown>> = {},
    page = currentRoute(),
  ): Promise<boolean> {
    if (!/^[a-z][a-z0-9_]{0,79}$/.test(eventName)) return Promise.resolve(false)
    const now = Date.now()
    const queue = parseQueue(this.storage)
    const event: AnalyticsEvent = {
      eventId: `evt-${now.toString(36)}-${Math.random().toString(36).slice(2, 12)}`,
      eventName,
      occurredAt: new Date(now).toISOString(),
      page,
      properties,
    }
    this.save([...queue, event])
    return this.flush()
  }
}
