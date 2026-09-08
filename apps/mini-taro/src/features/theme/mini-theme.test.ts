import { expect, it } from 'vitest'
import { createMiniThemeStore, miniThemeStorageKey } from './mini-theme-store'
import { themes } from './theme-catalog'
import { webThemes } from '../../web/web-themes'

function storage(value: unknown = '') {
  const values = new Map<string, unknown>([[miniThemeStorageKey, value]])
  return { getStorageSync: (key: string) => values.get(key), setStorageSync: (key: string, next: unknown) => { values.set(key, next) } }
}
it('restores a selected theme on the next application session', () => {
  const disk = storage()
  const first = createMiniThemeStore(disk)
  expect(first.select('alliance')).toBe(true)
  expect(createMiniThemeStore(disk).getSnapshot().id).toBe('alliance')
})
it.each(['invalid', null, { id: 'void' }, 4])('rejects invalid persisted selection %s', value => {
  expect(createMiniThemeStore(storage(value)).getSnapshot().id).toBe('horde')
})
it('updates every subscribed cached surface and removes unmounted subscribers', () => {
  const store = createMiniThemeStore(storage())
  const first: string[] = []; const second: string[] = []
  const unsubscribe = store.subscribe(() => first.push(store.getSnapshot().id))
  store.subscribe(() => second.push(store.getSnapshot().id))
  store.select('void'); unsubscribe(); store.select('venom')
  expect(first).toEqual(['void'])
  expect(second).toEqual(['void', 'venom'])
})
it('keeps selection usable when device storage is unavailable and reports persistence failure', () => {
  const store = createMiniThemeStore({ getStorageSync: () => { throw Error('denied') }, setStorageSync: () => { throw Error('full') } })
  expect(store.getSnapshot().id).toBe('horde')
  expect(store.select('void')).toBe(false)
  expect(store.getSnapshot().id).toBe('void')
})
it('offers the same seven theme metadata as Web without importing illustrations into Mini', () => {
  expect(themes).toHaveLength(7)
  expect(webThemes.map(({ id, name, color, accent, soft, sidebar }) => ({ id, name, color, accent, soft, sidebar }))).toEqual(themes)
  expect(themes.every(theme => !('image' in theme))).toBe(true)
})
