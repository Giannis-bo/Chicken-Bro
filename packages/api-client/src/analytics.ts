import { storageKey } from '@wow-mini/domain'

import type { StorageAdapter } from './storage'

const SESSION_TTL_MS = 30 * 60 * 1000

export interface AnalyticsClock {
  now(): number
  random(): number
}

const defaultClock: AnalyticsClock = {
  now: () => Date.now(),
  random: () => Math.random(),
}

export class AnalyticsIdentity {
  private sessionIdCache = ''

  constructor(
    private readonly storage: StorageAdapter,
    private readonly clock: AnalyticsClock = defaultClock,
  ) {}

  private randomId(prefix: string): string {
    return `${prefix}-${this.clock.now().toString(36)}-${this.clock.random().toString(36).slice(2, 10)}`
  }

  clientId(): string {
    const key = storageKey('analytics.clientId')
    const stored = this.storage.get<string>(key)
    if (stored) return stored
    const value = this.randomId('mp')
    this.storage.set(key, value)
    return value
  }

  sessionId(): string {
    if (this.sessionIdCache) return this.sessionIdCache
    const idKey = storageKey('analytics.sessionId')
    const startedKey = storageKey('analytics.sessionStartedAt')
    const stored = this.storage.get<string>(idKey)
    const startedAt = Number(this.storage.get<string | number>(startedKey) ?? 0)
    if (stored && startedAt > 0 && this.clock.now() - startedAt < SESSION_TTL_MS) {
      this.sessionIdCache = stored
      return stored
    }
    const value = this.randomId('session')
    this.sessionIdCache = value
    this.storage.set(idKey, value)
    this.storage.set(startedKey, String(this.clock.now()))
    return value
  }

  headers(platform = 'miniprogram'): Readonly<Record<string, string>> {
    return {
      'X-Wow-Client-Id': this.clientId(),
      'X-Wow-Session-Id': this.sessionId(),
      'X-Wow-Platform': platform,
    }
  }
}
