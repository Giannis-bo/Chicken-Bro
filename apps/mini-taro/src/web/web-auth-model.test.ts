import { describe, expect, it, vi } from 'vitest'

import type { WebLoginCreated, WebLoginStatusResponse } from '@wow-mini/domain'

import {
  WebAuthIntentFence,
  initialWebAuthState,
  reduceWebAuthState,
  selectWebLoginCreateAttempt,
  shouldDiscardWebLoginCreateAttempt,
  type WebAuthStateEvent,
} from './web-auth-model'

const validCreated: WebLoginCreated = {
  sessionId: '2d4d7f9a-3552-4f7e-8a4c-0d2b9b3a1f77',
  expiresAt: '2026-09-01T12:00:00.000Z',
  qrDataUrl: 'data:image/png;base64,iVBORw0KGgo=',
}

const validStatus = (status: WebLoginStatusResponse['status']): WebLoginStatusResponse => ({
  status,
  expiresAt: validCreated.expiresAt,
})

describe('Web auth browser state model', () => {
  it('transitions only from a real QR response to pending', () => {
    expect(reduceWebAuthState(initialWebAuthState, { type: 'created', payload: validCreated }))
      .toMatchObject({
        phase: 'qr_pending',
        sessionId: validCreated.sessionId,
        qrDataUrl: validCreated.qrDataUrl,
        polling: true,
      })

    expect(reduceWebAuthState(initialWebAuthState, {
      type: 'created',
      payload: { ...validCreated, qrDataUrl: 'placeholder' },
    })).toMatchObject({ phase: 'blocked', polling: false })
  })

  it('keeps the status machine honest across confirmation and terminal states', () => {
    const pending = reduceWebAuthState(initialWebAuthState, { type: 'created', payload: validCreated })
    const confirmed = reduceWebAuthState(pending, { type: 'status', payload: validStatus('confirmed') })
    expect(confirmed).toMatchObject({ phase: 'qr_confirmed', polling: false })

    const expired = reduceWebAuthState(confirmed, { type: 'status', payload: validStatus('expired') })
    expect(expired).toMatchObject({ phase: 'signed_out', polling: false, errorCode: 'WEB_LOGIN_EXPIRED' })

    const cancelled = reduceWebAuthState(confirmed, { type: 'status', payload: validStatus('cancelled') })
    expect(cancelled).toMatchObject({ phase: 'signed_out', polling: false, errorCode: 'WEB_LOGIN_CANCELLED' })

    const consumed = reduceWebAuthState(pending, { type: 'status', payload: validStatus('consumed') })
    expect(consumed).toMatchObject({ phase: 'checking', polling: false })

    const consumedWhileExchanging = reduceWebAuthState(confirmed, {
      type: 'status',
      payload: validStatus('consumed'),
    })
    expect(consumedWhileExchanging).toEqual(confirmed)

    const authenticated = reduceWebAuthState(confirmed, { type: 'authenticated' })
    expect(authenticated).toMatchObject({ phase: 'authenticated', polling: false })
  })

  it('never lets a late poll resurrect a terminal QR session', () => {
    const pending = reduceWebAuthState(initialWebAuthState, { type: 'created', payload: validCreated })
    const cancelled = reduceWebAuthState(pending, { type: 'status', payload: validStatus('cancelled') })
    const afterLatePending = reduceWebAuthState(cancelled, { type: 'status', payload: validStatus('pending') })
    expect(afterLatePending).toEqual(cancelled)

    const consumed = reduceWebAuthState(pending, { type: 'status', payload: validStatus('consumed') })
    const afterLateConfirmed = reduceWebAuthState(consumed, { type: 'status', payload: validStatus('confirmed') })
    expect(afterLateConfirmed).toEqual(consumed)
  })

  it('turns transport failures into a visible blocked state and logout into signed out', () => {
    const blocked = reduceWebAuthState(initialWebAuthState, {
      type: 'blocked',
      code: 'WECHAT_PROVIDER_UNAVAILABLE',
      message: '登录服务暂不可用',
    })
    expect(blocked).toMatchObject({
      phase: 'blocked',
      errorCode: 'WECHAT_PROVIDER_UNAVAILABLE',
      errorMessage: '登录服务暂不可用',
      polling: false,
    })

    const reset = reduceWebAuthState(blocked, { type: 'logout' })
    expect(reset).toMatchObject({ phase: 'signed_out', polling: false })
  })

  it('uses exactly the approved Web phases', () => {
    const phases = [
      initialWebAuthState.phase,
      reduceWebAuthState(initialWebAuthState, { type: 'signed_out' }).phase,
      reduceWebAuthState(initialWebAuthState, { type: 'created', payload: validCreated }).phase,
      reduceWebAuthState(
        reduceWebAuthState(initialWebAuthState, { type: 'created', payload: validCreated }),
        { type: 'status', payload: validStatus('confirmed') },
      ).phase,
      reduceWebAuthState(initialWebAuthState, { type: 'authenticated' }).phase,
      reduceWebAuthState(initialWebAuthState, { type: 'blocked' }).phase,
    ]
    expect(phases).toEqual([
      'checking',
      'signed_out',
      'qr_pending',
      'qr_confirmed',
      'authenticated',
      'blocked',
    ])
  })

  it('keeps browser verifier storage and event types explicit', () => {
    const eventTypes: WebAuthStateEvent['type'][] = [
      'created',
      'status',
      'authenticated',
      'blocked',
      'logout',
      'signed_out',
    ]
    expect(eventTypes).toEqual(['created', 'status', 'authenticated', 'blocked', 'logout', 'signed_out'])
  })

  it('reuses an uncertain QR creation identity until an explicit replacement', () => {
    const createKey = vi.fn()
      .mockReturnValueOnce('login-request-one')
      .mockReturnValueOnce('login-request-two')
    const verifier = 'A'.repeat(43)

    const first = selectWebLoginCreateAttempt(null, verifier, false, createKey)
    const retry = selectWebLoginCreateAttempt(first, verifier, false, createKey)
    const replacement = selectWebLoginCreateAttempt(first, verifier, true, createKey)

    expect(retry).toBe(first)
    expect(replacement).toEqual({
      browserVerifier: verifier,
      idempotencyKey: 'login-request-two',
    })
    expect(createKey).toHaveBeenCalledTimes(2)
  })

  it('discards only an explicitly unrecoverable QR creation identity', () => {
    expect(shouldDiscardWebLoginCreateAttempt('WEB_LOGIN_RESTART_REQUIRED')).toBe(true)
    expect(shouldDiscardWebLoginCreateAttempt('WECHAT_PROVIDER_UNAVAILABLE')).toBe(false)
    expect(shouldDiscardWebLoginCreateAttempt(undefined)).toBe(false)
  })

  it('lets only the latest asynchronous auth intent update browser state', () => {
    const fence = new WebAuthIntentFence()
    const initialCheck = fence.begin()
    expect(fence.isCurrent(initialCheck)).toBe(true)

    const qrLogin = fence.begin()
    expect(fence.isCurrent(initialCheck)).toBe(false)
    expect(fence.isCurrent(qrLogin)).toBe(true)
    expect(fence.capture()).toBe(qrLogin)

    fence.invalidate()
    expect(fence.isCurrent(qrLogin)).toBe(false)
  })
})
