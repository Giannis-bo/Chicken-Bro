import { describe, expect, it } from 'vitest'

import { GearRequestFence } from './gear-request-fence'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => { resolve = next })
  return { promise, resolve }
}

describe('GearRequestFence', () => {
  it('rejects a resolver and stat snapshot that finish after the draft is reset', async () => {
    const fence = new GearRequestFence()
    const resolver = deferred<string>()
    const stats = deferred<string>()
    const accepted: string[] = []
    const resolveToken = fence.beginResolve()
    const statToken = fence.beginStats()
    const resolveCompletion = resolver.promise.then((value) => {
      if (fence.isResolveCurrent(resolveToken)) accepted.push(value)
    })
    const statCompletion = stats.promise.then((value) => {
      if (fence.isStatsCurrent(statToken)) accepted.push(value)
    })

    fence.replaceDraft()
    resolver.resolve('stale resolver')
    stats.resolve('stale stats')
    await Promise.all([resolveCompletion, statCompletion])

    expect(accepted).toEqual([])
  })

  it('rejects an import that finishes after reset or a newer import begins', async () => {
    const fence = new GearRequestFence()
    const first = fence.beginImport()
    fence.replaceDraft()
    expect(fence.isImportCurrent(first)).toBe(false)

    const second = fence.beginImport()
    const third = fence.beginImport()
    expect(fence.isImportCurrent(second)).toBe(false)
    expect(fence.isImportCurrent(third)).toBe(true)
  })

  it('rejects an older import when a newer draft resolve begins', () => {
    const fence = new GearRequestFence()
    const importToken = fence.beginImport()

    fence.beginResolve()

    expect(fence.isImportCurrent(importToken)).toBe(false)
  })

  it('invalidates an in-flight stat request when canonical resolution restarts', () => {
    const fence = new GearRequestFence()
    const statToken = fence.beginStats()
    const resolveToken = fence.beginResolve()

    expect(fence.isStatsCurrent(statToken)).toBe(false)
    expect(fence.isResolveCurrent(resolveToken)).toBe(true)
  })

  it('classifies a resolver completion after reset as stale instead of failed', async () => {
    const fence = new GearRequestFence()
    const pending = deferred<string>()
    const completion = fence.runResolve(() => pending.promise)

    fence.replaceDraft()
    pending.resolve('late result')

    await expect(completion).resolves.toEqual({ status: 'stale' })
  })
})
