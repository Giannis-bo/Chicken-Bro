import cdn from './web-theme-cdn.json'
import { themes } from '../features/theme/theme-catalog'

const toWebTheme = (theme: typeof themes[number]) => ({
  ...theme,
  image: `${cdn.root}/${cdn.images[theme.id]}`,
})
export const webThemes = [toWebTheme(themes[0]), ...themes.slice(1).map(toWebTheme)] as const
export type WebThemeId = typeof webThemes[number]['id']
export const themeStorageKey = 'chickenbro.web.theme.v1'
export function resolveWebTheme(value: string | null) {
  return webThemes.find(theme => theme.id === value) ?? webThemes[0]
}
export function readWebTheme(): WebThemeId {
  try { return resolveWebTheme(localStorage.getItem(themeStorageKey)).id } catch { return 'horde' }
}
export function saveWebTheme(id: WebThemeId): boolean {
  try { localStorage.setItem(themeStorageKey, id); return true } catch { return false }
}
