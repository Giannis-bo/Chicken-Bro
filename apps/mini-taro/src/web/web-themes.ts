import horde from './assets/horde-bg-v2-clean.png'
import alliance from './assets/themes/alliance.png'
import maghar from './assets/themes/maghar-citadel.png'
import forsaken from './assets/themes/forsaken.png'
import voidArt from './assets/themes/void.png'
import deathwing from './assets/themes/deathwing.png'
import venom from './assets/themes/venom.png'

import { themes } from '../features/theme/theme-catalog'

export const webThemes = [
  { ...themes[0], image: horde },
  { ...themes[1], image: alliance },
  { ...themes[2], image: maghar },
  { ...themes[3], image: forsaken },
  { ...themes[4], image: voidArt },
  { ...themes[5], image: deathwing },
  { ...themes[6], image: venom },
] as const
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
