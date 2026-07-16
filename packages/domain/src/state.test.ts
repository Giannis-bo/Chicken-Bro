import { describe, expect, it } from 'vitest'

import { apiResultToRouteState, isReadyState, trustForLocal } from './index'

describe('route trust state mapping', () => {
  it('maps a backend result to verified ready state', () => {
    const state = apiResultToRouteState({ payload: { count: 2 }, fromFallback: false, error: '' })
    expect(state.state).toBe('ready')
    expect(isReadyState(state)).toBe(true)
  })

  it('never promotes fallback payload to ready', () => {
    const state = apiResultToRouteState({ payload: { dps: 123 }, fromFallback: true, error: 'offline' })
    expect(state.state).toBe('blocked')
    expect(isReadyState(state)).toBe(false)
  })

  it('retains previously verified data only as stale', () => {
    const state = apiResultToRouteState(
      { payload: { count: 0 }, fromFallback: true, error: 'timeout' },
      { previous: { count: 4 } },
    )
    expect(state).toMatchObject({ state: 'stale', data: { count: 4 }, staleReason: 'timeout' })
  })

  it('labels local profile and template state explicitly', () => {
    expect(trustForLocal()).toMatchObject({ level: 'local_only' })
  })
})
