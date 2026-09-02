import type { TabBarItem } from '@wow-mini/design-system/components/TabBar'

export const tabBarItems: readonly TabBarItem[] = [
  {
    pagePath: 'pages/chickenbro/index',
    label: '队长',
    glyphAssetId: 'product-tab-glyph.captain',
    glyphSlotId: 'asset_slot.product-tab-glyphs',
    fallbackGlyphAssetId: 'product-tab-simulator-icon.default',
    fallbackGlyphSlotId: 'asset_slot.product-tab-simulator-icon',
  },
  {
    pagePath: 'pages/simc/index',
    label: 'SimC',
    glyphAssetId: 'product-tab-glyph.spec',
    glyphSlotId: 'asset_slot.product-tab-glyphs',
    fallbackGlyphAssetId: 'product-tab-builds-icon.default',
    fallbackGlyphSlotId: 'asset_slot.product-tab-builds-icon',
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
