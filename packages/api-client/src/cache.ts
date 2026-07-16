export interface CacheClock {
  now(): number
}

const systemClock: CacheClock = { now: () => Date.now() }

export interface CacheEntry<T> {
  value: T
  storedAt: number
  expiresAt: number
}

export interface CacheLookup<T> {
  value: T
  ageMs: number
  stale: boolean
}

export class TimedCache {
  private readonly values = new Map<string, CacheEntry<unknown>>()

  constructor(private readonly clock: CacheClock = systemClock) {}

  get<T>(key: string, allowStale = false): CacheLookup<T> | undefined {
    const entry = this.values.get(key)
    if (!entry) return undefined
    const stale = this.clock.now() >= entry.expiresAt
    if (stale && !allowStale) return undefined
    return {
      value: entry.value as T,
      ageMs: Math.max(0, this.clock.now() - entry.storedAt),
      stale,
    }
  }

  set<T>(key: string, value: T, ttlMs: number): void {
    const storedAt = this.clock.now()
    this.values.set(key, {
      value,
      storedAt,
      expiresAt: storedAt + Math.max(0, ttlMs),
    })
  }

  delete(key: string): void {
    this.values.delete(key)
  }

  clear(): void {
    this.values.clear()
  }
}
