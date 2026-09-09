import { describe, expect, it } from 'vitest'

import { clientAuthRequest, type ClientAuthContext } from './auth-context'


describe('Web auth context', () => {
  it('rejects retired auth contexts before transport', () => {
    expect(() => clientAuthRequest({ kind: 'mini', accessToken: 'old-token' } as unknown as ClientAuthContext, { mutating: true })).toThrow()
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
    expect(() => clientAuthRequest({ kind: 'web', csrfToken: '' }, { mutating: false })).toThrow()
    expect(() => clientAuthRequest({ kind: 'web', csrfToken: 'bad token' }, { mutating: true })).toThrow()
  })
})
