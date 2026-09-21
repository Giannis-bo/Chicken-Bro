// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { normalizeWebUrl, readWebView, webViewHref } from './web-routing'

afterEach(() => window.history.replaceState(null, '', '/'))

describe('Web short routes', () => {
  it('keeps POE2 workbench navigation under a candidate base', () => {
    const url = new URL('https://chickenbro.cloud/poe2-candidate/?game=poe2&view=builds')
    expect(readWebView(url, '/poe2-candidate')).toBe('poe2')
    expect(webViewHref('poe2', url, '/poe2-candidate')).toBe('/poe2-candidate/poe2?game=poe2')
  })
  it.each([
    ['/#/pages/chickenbro/index', '/', 'chat'],
    ['/?view=simc#/pages/chickenbro/index', '/simc', 'simc'],
    ['/simc/', '/simc', 'simc'],
    ['/?view=faq#/pages/chickenbro/index', '/?view=faq', 'faq'],
    ['/?view=simc&source=bookmark#/pages/chickenbro/index', '/simc?source=bookmark', 'simc'],
  ] as const)('normalizes %s without adding a history entry', (input, expected, view) => {
    window.history.replaceState({ idx: 2 }, '', input)
    const length = window.history.length
    normalizeWebUrl()
    expect(window.location.pathname + window.location.search + window.location.hash).toBe(expected)
    expect(readWebView()).toBe(view)
    expect(window.history.state).toEqual({ idx: 2 })
    expect(window.history.length).toBe(length)
  })

  it('keeps preview navigation under its configured base and preserves unrelated anchors', () => {
    const url = new URL('https://chickenbro.cloud/web-candidate/?view=simc#settings')
    expect(webViewHref(readWebView(url, '/web-candidate'), url, '/web-candidate')).toBe('/web-candidate/simc#settings')
    expect(readWebView(new URL('https://chickenbro.cloud/web-candidate/simc'), '/web-candidate')).toBe('simc')
    expect(webViewHref('chat', url, '/web-candidate')).toBe('/web-candidate/#settings')
  })
})
