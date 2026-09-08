import Taro from '@tarojs/taro'
import { useSyncExternalStore, type CSSProperties } from 'react'
import { createMiniThemeStore } from './mini-theme-store'

const miniThemeStore = createMiniThemeStore({
  getStorageSync: key => Taro.getStorageSync(key),
  setStorageSync: (key, value) => Taro.setStorageSync(key, value),
})

export function useMiniTheme() {
  const theme = useSyncExternalStore(miniThemeStore.subscribe, miniThemeStore.getSnapshot, miniThemeStore.getSnapshot)
  const themeStyle = {
    '--mini-theme-accent': theme.accent,
    '--mini-theme-soft': theme.soft,
    '--mini-theme-sidebar': theme.sidebar,
  } as CSSProperties
  return { theme, themeStyle, setTheme: miniThemeStore.select }
}
