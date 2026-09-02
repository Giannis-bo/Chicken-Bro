export interface CoreTabItem {
  pagePath: string
  label: string
  glyph: string
}

export const tabBarItems: readonly CoreTabItem[] = [
  {
    pagePath: 'pages/chickenbro/index',
    label: '队长',
    glyph: '聊',
  },
  {
    pagePath: 'pages/simc/index',
    label: 'SimC',
    glyph: 'S',
  },
]

export function normalizeTabRoute(path: string): string {
  return path.replace(/^\/?#?\/?/, '').split('?')[0] ?? ''
}

export function isTabRoute(path: string): boolean {
  const normalized = normalizeTabRoute(path)
  return tabBarItems.some((item) => item.pagePath === normalized)
}

export function resolveActiveTabRoute(
  candidates: readonly (string | null | undefined)[],
  fallback = tabBarItems[0]?.pagePath ?? 'pages/chickenbro/index',
): string {
  for (const candidate of candidates) {
    if (!candidate) continue
    const normalized = normalizeTabRoute(candidate)
    if (isTabRoute(normalized)) return normalized
  }
  return normalizeTabRoute(fallback)
}
