// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { readWebTheme, themeStorageKey, webThemes } from './web-themes'

it('loads all seven illustrations from an immutable HTTPS CDN release', () => {
  expect(webThemes).toHaveLength(7)
  expect(new Set(webThemes.map(theme => theme.image)).size).toBe(7)
  for (const theme of webThemes) {
    const url = new URL(theme.image)
    expect(url.origin).toBe('https://static.chickenbro.cloud')
    expect(url.pathname).toMatch(/^\/wow-assets\/releases\/2026-09-08-web-themes-v1\/[a-z0-9-]+\.png$/u)
  }
})

afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })
it('falls back to Horde for removed, corrupt or missing preferences', () => {
  for (const value of ['illidan', '{broken', '', 'unknown']) {
    localStorage.setItem(themeStorageKey, value)
    expect(readWebTheme()).toBe('horde')
  }
  localStorage.clear()
  expect(readWebTheme()).toBe('horde')
})
it('still opens with the default theme if reading storage is denied', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
  expect(readWebTheme()).toBe('horde')
})
