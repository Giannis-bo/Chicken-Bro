import { describe, expect, it } from 'vitest'

import { resolveTrustedMediaLoadState } from './useTrustedMediaLoadState'

describe('resolveTrustedMediaLoadState', () => {
  it('keeps a warm-cache load associated with its URL', () => {
    expect(resolveTrustedMediaLoadState('https://media.example/icon.jpg', 'https://media.example/icon.jpg', '')).toEqual({
      failed: false,
      loaded: true,
      visible: true,
    })
  })

  it('does not leak load state across a changed URL', () => {
    expect(resolveTrustedMediaLoadState('https://media.example/new.jpg', 'https://media.example/old.jpg', '')).toEqual({
      failed: false,
      loaded: false,
      visible: false,
    })
  })

  it('lets the current URL failure win over an earlier load', () => {
    expect(resolveTrustedMediaLoadState(
      'https://media.example/icon.jpg',
      'https://media.example/icon.jpg',
      'https://media.example/icon.jpg',
    )).toEqual({
      failed: true,
      loaded: true,
      visible: false,
    })
  })
})
