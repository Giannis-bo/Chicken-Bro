import { describe, expect, it } from 'vitest'

import {
  isQqLoginCreated,
  isConfirmResponse,
  isLogoutResponse,
  isMeResponse,
  isMiniExchangeResponse,
  isValidBrowserVerifier,
  isWebLoginCreated,
  isWebLoginExchangeResponse,
  isWebLoginStatusResponse,
} from './web-auth'

describe('QQ Web login contract', () => {
  it('accepts only the exact official HTTPS authorize endpoint', () => {
    expect(isQqLoginCreated({ authorizationUrl: 'https://graph.qq.com/oauth2.0/authorize?client_id=1905584243&state=abc', requestId: 'r1' })).toBe(true)
    for (const authorizationUrl of [
      'http://graph.qq.com/oauth2.0/authorize?state=abc',
      'https://evil.example/oauth2.0/authorize?state=abc',
      'https://graph.qq.com:444/oauth2.0/authorize?state=abc',
      'https://user@graph.qq.com/oauth2.0/authorize?state=abc',
      'https://graph.qq.com/oauth2.0/authorize/extra?state=abc',
      'https://graph.qq.com/oauth2.0/authorize?state=abc#fragment',
    ]) expect(isQqLoginCreated({ authorizationUrl, requestId: 'r1' })).toBe(false)
  })

  it('accepts an allowlisted QQ avatar URL and rejects other profile URLs', () => {
    expect(isMeResponse({ connected: true, displayName: 'QQ 队长', avatarUrl: 'https://q.qlogo.cn/headimg_dl?dst_uin=1' })).toBe(true)
    expect(isMeResponse({ connected: true, displayName: 'QQ 队长', avatarUrl: 'https://thirdqq.qlogo.cn/g?b=oidb' })).toBe(true)
    expect(isMeResponse({ connected: true, displayName: 'QQ 队长', avatarUrl: 'https://evil.example/avatar.png' })).toBe(false)
  })
})

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

  it('rejects unexpected fields from every identity response', () => {
    const responses: ReadonlyArray<[(value: unknown) => boolean, Record<string, unknown>]> = [
      [isWebLoginCreated, {
        sessionId: '00000000-0000-4000-8000-000000000000',
        expiresAt: '2026-09-01T10:00:00.000Z',
        qrDataUrl: 'data:image/png;base64,AA==',
      }],
      [isWebLoginStatusResponse, {
        status: 'pending',
        expiresAt: '2026-09-01T10:00:00.000Z',
      }],
      [isWebLoginExchangeResponse, { authenticated: true }],
      [isMiniExchangeResponse, {
        accessToken: 'mini-secret-token',
        expiresAt: '2026-09-01T10:00:00.000Z',
      }],
      [isConfirmResponse, { confirmed: true }],
      [isMeResponse, { connected: true, displayName: '已连接微信账号' }],
      [isLogoutResponse, { loggedOut: true }],
    ]

    for (const [validate, payload] of responses) {
      expect(validate(payload)).toBe(true)
      expect(validate({ ...payload, userId: 'must-not-cross-the-boundary' })).toBe(false)
      expect(validate({ ...payload, openid: 'must-not-cross-the-boundary' })).toBe(false)
    }
  })

  it('rejects malformed or unbounded Mini bearer credentials', () => {
    const base = { expiresAt: '2026-09-01T10:00:00.000Z' }
    expect(isMiniExchangeResponse({ ...base, accessToken: 'x'.repeat(16) })).toBe(true)
    expect(isMiniExchangeResponse({ ...base, accessToken: 'contains space token' })).toBe(false)
    expect(isMiniExchangeResponse({ ...base, accessToken: 'x'.repeat(513) })).toBe(false)
  })

  it('accepts the complete persisted public display-name range', () => {
    expect(isMeResponse({ connected: true, displayName: '名'.repeat(256) })).toBe(true)
    expect(isMeResponse({ connected: true, displayName: '名'.repeat(257) })).toBe(false)
  })
})
