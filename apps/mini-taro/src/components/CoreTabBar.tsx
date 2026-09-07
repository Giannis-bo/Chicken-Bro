import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useEffect, useState } from 'react'

import type { CoreTabItem } from '../tab-bar-items'

import styles from './CoreTabBar.module.scss'

export interface CoreTabBarProps {
  currentPath: string
  items: readonly CoreTabItem[]
  onSelect: (pagePath: string) => void
}

function normalizePath(value: string): string {
  return value.replace(/^\//u, '')
}

export function CoreTabBar({ currentPath, items, onSelect }: CoreTabBarProps) {
  const [keyboardVisible, setKeyboardVisible] = useState(false)
  useEffect(() => {
    const update = ({ height }: { height: number }) => setKeyboardVisible(height > 0)
    Taro.onKeyboardHeightChange?.(update)
    return () => { Taro.offKeyboardHeightChange?.(update) }
  }, [])
  const normalizedCurrent = normalizePath(currentPath)
  if (keyboardVisible) return null
  return (
    <View className={styles['root'] ?? ''} data-owner="core-tab-bar">
      <View className={styles['list'] ?? ''} data-role="core-tab-list">
        {items.map((item) => {
          const selected = normalizePath(item.pagePath) === normalizedCurrent
          return (
            <View
              key={item.pagePath}
              className={`${styles['item'] ?? ''} ${selected ? styles['selected'] ?? '' : ''}`}
              aria-label={item.label}
              aria-current={selected ? 'page' : undefined}
              data-role="core-tab-item"
              data-selected={selected ? 'true' : 'false'}
              role="button"
              onClick={() => onSelect(item.pagePath)}
            >
              <Text className={styles['label'] ?? ''}>{item.label}</Text>
            </View>
          )
        })}
      </View>
    </View>
  )
}
