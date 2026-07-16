import { View } from '@tarojs/components'

import type { AssetSlotId, ProductionAssetId } from '@wow-mini/assets-manifest'

import { runtimeSafeAreaStyle } from '../runtime-safe-area'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { dataSelectorClass, selectorClass, styleSelectorClass } from './selector-markers'

import styles from './TabBar.module.scss'

export interface TabBarItem {
  pagePath: string
  label: string
  glyphAssetId: ProductionAssetId
  glyphSlotId: AssetSlotId
  fallbackGlyphAssetId: ProductionAssetId
  fallbackGlyphSlotId: AssetSlotId
}

export interface TabBarProps {
  currentPath: string
  items: readonly TabBarItem[]
  onSelect: (pagePath: string) => void
}

function normalizePath(value: string): string {
  return value.replace(/^\//, '')
}

export function TabBar({ currentPath, items, onSelect }: TabBarProps) {
  const normalizedCurrent = normalizePath(currentPath)
  return (
    <View
      className={selectorClass(styles['root'] ?? '', styleSelectorClass('product-tab-bar'))}
      data-owner="product-tab-bar"
      style={runtimeSafeAreaStyle()}
    >
      <View
        className={selectorClass(
          styles['list'] ?? '',
          styleSelectorClass('product-tab-list'),
        )}
        data-role="product-tab-list"
      >
        {items.map((item) => {
          const selected = normalizePath(item.pagePath) === normalizedCurrent

          return (
            <View
              key={item.pagePath}
              className={selectorClass(
                styles['item'] ?? '',
                selected ? styles['selected'] : undefined,
                styleSelectorClass('product-tab-item'),
                dataSelectorClass('selected', selected),
              )}
              aria-label={item.label}
              aria-current={selected ? 'page' : undefined}
              data-selected={selected ? 'true' : 'false'}
              data-state={selected ? 'active' : 'inactive'}
              role="button"
              onClick={() => onSelect(item.pagePath)}
            >
              <ProductionAssetGlyph
                assetId={item.glyphAssetId}
                className={selectorClass(
                  styles['icon'] ?? '',
                  styleSelectorClass('product-tab-icon'),
                )}
                dataRole="product-tab-glyph"
                fallbackAssetId={item.fallbackGlyphAssetId}
                fallbackSlotId={item.fallbackGlyphSlotId}
                slotId={item.glyphSlotId}
              />
              <View
                className={selectorClass(
                  styles['label'] ?? '',
                  styleSelectorClass('product-tab-label'),
                )}
              >
                {item.label}
              </View>
            </View>
          )
        })}
      </View>
    </View>
  )
}
