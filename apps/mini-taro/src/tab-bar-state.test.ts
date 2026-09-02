import { describe, expect, it, vi } from 'vitest'

import { createActiveTabRouteStore } from './tab-bar-state'

describe('active tab route store', () => {
  it('publishes a tab root identity and normalizes its path', () => {
    const store = createActiveTabRouteStore()
    const listener = vi.fn()
    store.subscribe(listener)

    expect(store.set('/pages/simc/index?from=chat')).toBe(true)
    expect(store.get()).toBe('pages/simc/index')
    expect(listener).toHaveBeenCalledWith('pages/simc/index')
  })

  it('ignores non-tab routes and stops notifying after unsubscribe', () => {
    const store = createActiveTabRouteStore()
    const listener = vi.fn()
    const unsubscribe = store.subscribe(listener)

    expect(store.set('pages/simc/tasks')).toBe(false)
    expect(store.get()).toBeNull()
    unsubscribe()
    expect(store.set('pages/chickenbro/index')).toBe(true)
    expect(listener).not.toHaveBeenCalled()
  })
})
