import { resolveTheme, type ThemeId } from './theme-catalog'

export const miniThemeStorageKey = 'chickenbro.mini.theme.v1'
interface ThemeStorage {
  getStorageSync: (key: string) => unknown
  setStorageSync: (key: string, value: string) => void
}

export function createMiniThemeStore(storage: ThemeStorage) {
  let theme = resolveTheme(null)
  let loaded = false
  const listeners = new Set<() => void>()
  const getSnapshot = () => {
    if (!loaded) {
      loaded = true
      try { theme = resolveTheme(storage.getStorageSync(miniThemeStorageKey)) } catch { /* Keep the default when storage is unavailable. */ }
    }
    return theme
  }
  return {
    getSnapshot,
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    select(id: ThemeId): boolean {
      loaded = true
      theme = resolveTheme(id)
      let saved = true
      try { storage.setStorageSync(miniThemeStorageKey, theme.id) } catch { saved = false }
      for (const listener of listeners) listener()
      return saved
    },
  }
}
