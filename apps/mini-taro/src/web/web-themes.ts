import horde from './assets/horde-bg-v2-clean.png'
import alliance from './assets/themes/alliance.png'
import maghar from './assets/themes/maghar-citadel.png'
import forsaken from './assets/themes/forsaken.png'
import voidArt from './assets/themes/void.png'
import deathwing from './assets/themes/deathwing.png'
import venom from './assets/themes/venom.png'

export const webThemes = [
  { id: 'horde', name: '为了部落', color: '部落红', image: horde, accent: '#9e5145', soft: '#f2e5e1', sidebar: '#f8f3f1' },
  { id: 'alliance', name: '为了联盟', color: '联盟蓝', image: alliance, accent: '#466b94', soft: '#e7eef6', sidebar: '#f2f5f9' },
  { id: 'maghar', name: '兽人永不为奴', color: '玛格汉棕', image: maghar, accent: '#855f43', soft: '#efe6dc', sidebar: '#f7f3ee' },
  { id: 'forsaken', name: '被遗忘者的挽歌', color: '亡灵暗灰', image: forsaken, accent: '#626574', soft: '#e9eaee', sidebar: '#f3f3f6' },
  { id: 'void', name: '至暗之夜', color: '虚空紫', image: voidArt, accent: '#78578f', soft: '#eee6f4', sidebar: '#f7f3fa' },
  { id: 'deathwing', name: '大地的裂变', color: '黑曜石', image: deathwing, accent: '#4e5055', soft: '#e7e7e9', sidebar: '#f2f2f3' },
  { id: 'venom', name: '乌拉特克的诅咒', color: '剧毒绿', image: venom, accent: '#587541', soft: '#e8efdf', sidebar: '#f3f6ee' },
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
