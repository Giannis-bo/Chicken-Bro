import type { TabBarItem } from '@wow-mini/design-system/components/TabBar'

export const tabBarItems: readonly TabBarItem[] = [
  {
    pagePath: 'pages/news/news',
    label: '资讯',
    glyphAssetId: 'product-tab-glyph.news',
    glyphSlotId: 'asset_slot.product-tab-glyphs',
    fallbackGlyphAssetId: 'product-tab-news-icon.default',
    fallbackGlyphSlotId: 'asset_slot.product-tab-news-icon',
  },
  {
    pagePath: 'pages/builds/builds',
    label: '专精',
    glyphAssetId: 'product-tab-glyph.spec',
    glyphSlotId: 'asset_slot.product-tab-glyphs',
    fallbackGlyphAssetId: 'product-tab-builds-icon.default',
    fallbackGlyphSlotId: 'asset_slot.product-tab-builds-icon',
  },
  {
    pagePath: 'pages/simulator/simulator',
    label: '队长',
    glyphAssetId: 'product-tab-glyph.captain',
    glyphSlotId: 'asset_slot.product-tab-glyphs',
    fallbackGlyphAssetId: 'product-tab-simulator-icon.default',
    fallbackGlyphSlotId: 'asset_slot.product-tab-simulator-icon',
  },
  {
    pagePath: 'pages/profile/profile',
    label: '我的',
    glyphAssetId: 'product-tab-glyph.profile',
    glyphSlotId: 'asset_slot.product-tab-glyphs',
    fallbackGlyphAssetId: 'product-tab-profile-icon.default',
    fallbackGlyphSlotId: 'asset_slot.product-tab-profile-icon',
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
  fallback = tabBarItems[0]?.pagePath ?? 'pages/news/news',
): string {
  for (const candidate of candidates) {
    if (!candidate) continue
    const normalized = normalizeTabRoute(candidate)
    if (isTabRoute(normalized)) return normalized
  }
  return normalizeTabRoute(fallback)
}
