// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { readWebTheme, themeStorageKey } from './web-themes'

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
