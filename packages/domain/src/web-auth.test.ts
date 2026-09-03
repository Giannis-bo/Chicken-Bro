import { describe, expect, it } from 'vitest'

import {
  isValidBrowserVerifier,
  isWebLoginCreated,
  isWebLoginStatusResponse,
} from './web-auth'

describe('web auth domain contracts', () => {
  it('accepts only a bounded verifier and a non-placeholder PNG or JPEG response', () => {
    expect(isValidBrowserVerifier('A'.repeat(43))).toBe(true)
    expect(isValidBrowserVerifier('too-short')).toBe(false)
    expect(isValidBrowserVerifier('contains+slash/'.repeat(4))).toBe(false)

    expect(isWebLoginCreated({
      sessionId: '00000000-0000-4000-8000-000000000000',
      expiresAt: '2026-09-01T10:00:00.000Z',
      qrDataUrl: 'data:image/png;base64,AA==',
    })).toBe(true)
    expect(isWebLoginCreated({
      sessionId: '00000000-0000-4000-8000-000000000000',
      expiresAt: '2026-09-01T10:00:00.000Z',
      qrDataUrl: 'data:image/jpeg;base64,/9j/AA==',
    })).toBe(true)
    expect(isWebLoginCreated({
      sessionId: '00000000-0000-4000-8000-000000000000',
      expiresAt: '2026-09-01T10:00:00.000Z',
      sceneTicket: 'raw',
    })).toBe(false)
    expect(isWebLoginCreated({
      sessionId: '00000000-0000-4000-8000-000000000000',
      expiresAt: '2026-09-01T10:00:00.000Z',
      qrDataUrl: 'placeholder',
    })).toBe(false)
  })

  it('accepts only the public status vocabulary', () => {
    expect(isWebLoginStatusResponse({
      status: 'pending',
      expiresAt: '2026-09-01T10:00:00.000Z',
      requestId: 'request-1',
    })).toBe(true)
    expect(isWebLoginStatusResponse({
      status: 'consumed',
      expiresAt: '2026-09-01T10:00:00.000Z',
    })).toBe(true)
    expect(isWebLoginStatusResponse({
      status: 'exchanged',
      expiresAt: '2026-09-01T10:00:00.000Z',
    })).toBe(false)
    expect(isWebLoginStatusResponse({
      status: 'bound',
      expiresAt: '2026-09-01T10:00:00.000Z',
    })).toBe(false)
  })
})
