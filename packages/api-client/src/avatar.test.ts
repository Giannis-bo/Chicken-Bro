import { describe, expect, it, vi } from 'vitest'
import { isAvatarResponse } from '@wow-mini/domain'
import { createAvatarClient } from './avatar'
import type { ApiTransport } from './transport'

describe('account avatar transport', () => {
  it('uses authenticated owner routes and keeps Mini/Web credentials independent', async () => {
    const request = vi.fn().mockResolvedValue({ payload: { avatarDataUrl: null }, fromFallback: false })
    const client = createAvatarClient({ request } as unknown as ApiTransport)
    const mini = { kind: 'mini' as const, accessToken: 'mini-token' }
    const web = { kind: 'web' as const, csrfToken: 'csrf-token' }
    await client.get(mini)
    await client.get(web)
    await client.set('data:image/png;base64,AAAA', mini)
    expect(request.mock.calls.map(([path, options]) => [path, options.method, options.credentials, options.baseUrl, options.auth])).toEqual([
      ['/api/v2/me/avatar', 'GET', 'omit', 'default', mini],
      ['/api/v2/me/avatar', 'GET', 'include', 'web-auth', web],
      ['/api/v2/me/avatar', 'PUT', 'omit', 'default', mini],
    ])
    expect(request.mock.calls[2]?.[1].data).toEqual({ avatarDataUrl: 'data:image/png;base64,AAAA' })
  })
  it('rejects remote URLs, executable image formats, huge payloads and identity leakage', () => {
    expect(isAvatarResponse({ avatarDataUrl: null })).toBe(true)
    expect(isAvatarResponse({ avatarDataUrl: 'data:image/jpeg;base64,/9j/AA==' })).toBe(true)
    for (const avatarDataUrl of ['https://avatar.example/image', 'data:image/svg+xml;base64,AAA=', 'data:image/png;base64,' + 'A'.repeat(350000)]) {
      expect(isAvatarResponse({ avatarDataUrl })).toBe(false)
    }
    expect(isAvatarResponse({ avatarDataUrl: null, userId: 'private' })).toBe(false)
  })
})
