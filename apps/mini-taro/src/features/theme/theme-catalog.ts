export const themes = [
  { id: 'horde', name: '为了部落', color: '部落红', accent: '#9e5145', soft: '#f2e5e1', sidebar: '#f8f3f1' },
  { id: 'alliance', name: '为了联盟', color: '联盟蓝', accent: '#466b94', soft: '#e7eef6', sidebar: '#f2f5f9' },
  { id: 'maghar', name: '兽人永不为奴', color: '玛格汉棕', accent: '#855f43', soft: '#efe6dc', sidebar: '#f7f3ee' },
  { id: 'forsaken', name: '被遗忘者的挽歌', color: '亡灵暗灰', accent: '#626574', soft: '#e9eaee', sidebar: '#f3f3f6' },
  { id: 'void', name: '至暗之夜', color: '虚空紫', accent: '#78578f', soft: '#eee6f4', sidebar: '#f7f3fa' },
  { id: 'deathwing', name: '大地的裂变', color: '黑曜石', accent: '#4e5055', soft: '#e7e7e9', sidebar: '#f2f2f3' },
  { id: 'venom', name: '乌拉特克的诅咒', color: '剧毒绿', accent: '#587541', soft: '#e8efdf', sidebar: '#f3f6ee' },
] as const
export type ThemeId = typeof themes[number]['id']
export type Theme = typeof themes[number]
export function resolveTheme(value: unknown): Theme {
  return themes.find(theme => theme.id === value) ?? themes[0]
}
