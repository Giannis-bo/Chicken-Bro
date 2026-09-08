import { useState } from 'react'
import Taro from '@tarojs/taro'
import { Button, Text, View } from '@tarojs/components'
import styles from './MiniSimcTaskId.module.scss'

export default function MiniSimcTaskId({ id }: { id: string }) {
  const [feedback, setFeedback] = useState('')
  const copy = async () => {
    try {
      await Taro.setClipboardData({ data: id })
      setFeedback('已复制任务 ID')
    } catch {
      setFeedback('复制失败，请长按任务 ID 复制')
    }
  }
  return <View className={styles['taskId'] ?? ''} onClick={event => event.stopPropagation()}>
    <Text selectable className={styles['value'] ?? ''}>任务 ID：{id}</Text>
    <Button className={styles['copy'] ?? ''} size="mini" aria-label={`复制任务 ID ${id}`} onClick={event => { event.stopPropagation(); void copy() }}>复制 ID</Button>
    {feedback ? <Text className={styles['feedback'] ?? ''} aria-live="polite">{feedback}</Text> : null}
  </View>
}
