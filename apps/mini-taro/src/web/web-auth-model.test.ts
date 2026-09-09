// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { loginErrorCopy, readAndClearLoginError } from './web-auth-model'

describe('QQ callback landing', () => {
  it('translates fixed callback errors and clears only loginError', () => {
    window.history.replaceState(null, '', '/simc?foo=1&loginError=QQ_LOGIN_CANCELLED#report')
    expect(readAndClearLoginError()).toBe(loginErrorCopy.QQ_LOGIN_CANCELLED)
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/simc?foo=1#report')
  })
  it('does not display arbitrary callback text', () => {
    window.history.replaceState(null, '', '/?loginError=secret-provider-diagnostic')
    expect(readAndClearLoginError()).toBe(loginErrorCopy.QQ_LOGIN_FAILED)
    expect(window.location.search).toBe('')
  })
})
