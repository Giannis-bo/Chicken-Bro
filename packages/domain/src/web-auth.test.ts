import { describe, expect, it } from 'vitest'

import {
  isQqLoginCreated,
  isLogoutResponse,
  isMeResponse,
  isWebLoginExchangeResponse,
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

describe('Web identity response boundaries', () => {
  it('rejects ownership, provider tokens and extra response fields', () => {
    for (const [validate, payload] of [
      [isQqLoginCreated, { authorizationUrl: 'https://graph.qq.com/oauth2.0/authorize?state=abc' }],
      [isWebLoginExchangeResponse, { authenticated: true }],
      [isMeResponse, { connected: true, displayName: 'QQ 用户' }],
      [isLogoutResponse, { loggedOut: true }],
    ] as const) {
      expect(validate(payload)).toBe(true)
      for (const key of ['userId', 'openid', 'accessToken']) expect(validate({ ...payload, [key]: 'private' })).toBe(false)
    }
  })
  it('bounds the persisted display name', () => {
    expect(isMeResponse({ connected: true, displayName: '名'.repeat(256) })).toBe(true)
    expect(isMeResponse({ connected: true, displayName: '名'.repeat(257) })).toBe(false)
  })
})
