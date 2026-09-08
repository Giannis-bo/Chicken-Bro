import { Button, Text, View } from '@tarojs/components'
import { useState } from 'react'
import { themes } from './theme-catalog'
import { useMiniTheme } from './use-mini-theme'
import styles from './MiniThemePicker.module.scss'

export function MiniThemePicker() {
  const { theme, themeStyle, setTheme } = useMiniTheme()
  const [saveFailed, setSaveFailed] = useState(false)
  return (
    <View className={styles['root'] ?? ''} style={themeStyle}>
      <Text className={styles['title'] ?? ''}>主题</Text>
      <View className={styles['choices'] ?? ''}>
        {themes.map(choice => (
          <Button key={choice.id} className={`${styles['choice']} ${choice.id === theme.id ? styles['selected'] : ''}`}
            aria-label={`${choice.name}，${choice.color}${choice.id === theme.id ? '，已选择' : ''}`}
            data-theme-choice={choice.id} onClick={() => setSaveFailed(!setTheme(choice.id))}>
            <View className={styles['swatch'] ?? ''} style={{ backgroundColor: choice.accent }} />
            <View className={styles['copy'] ?? ''}><Text className={styles['name'] ?? ''}>{choice.name}</Text><Text className={styles['color'] ?? ''}>{choice.color}</Text></View>
            {choice.id === theme.id && <Text className={styles['check'] ?? ''}>✓</Text>}
          </Button>
        ))}
      </View>
      <Text className={styles['hint'] ?? ''}>{saveFailed ? '主题已切换，但未能保存；下次进入请重新选择。' : '主题保存在当前设备，可随时切换。'}</Text>
    </View>
  )
}
export default MiniThemePicker
