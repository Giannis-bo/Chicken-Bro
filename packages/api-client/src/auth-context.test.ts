import { describe, expect, it } from 'vitest'

import { clientAuthRequest, type ClientAuthContext } from './auth-context'


describe('formal dual-client auth context', () => {
  it('keeps Mini Bearer explicit and never enables Cookie credentials', () => {
    const auth: ClientAuthContext = { kind: 'mini', accessToken: 'mini-token' }

    expect(clientAuthRequest(auth, { mutating: true })).toEqual({
      header: { Authorization: 'Bearer mini-token' },
      credentials: 'omit',
      baseUrl: 'default',
    })
  })

  it('uses Web Cookie credentials and adds CSRF only for mutations', () => {
    const auth: ClientAuthContext = { kind: 'web', csrfToken: 'web-csrf' }

    expect(clientAuthRequest(auth, { mutating: false })).toEqual({
      header: {},
      credentials: 'include',
      baseUrl: 'web-auth',
    })
    expect(clientAuthRequest(auth, { mutating: true })).toEqual({
      header: { 'X-CSRF-Token': 'web-csrf' },
      credentials: 'include',
      baseUrl: 'web-auth',
    })
  })

  it('rejects empty or whitespace-bearing credentials before transport', () => {
    expect(() => clientAuthRequest({ kind: 'mini', accessToken: '' }, { mutating: false })).toThrow()
    expect(() => clientAuthRequest({ kind: 'web', csrfToken: 'bad token' }, { mutating: true })).toThrow()
  })
})
