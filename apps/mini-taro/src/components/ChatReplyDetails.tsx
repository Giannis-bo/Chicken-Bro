import { Button, Text, View } from '@tarojs/components'
import { useEffect, useState } from 'react'
import styles from './ChatReplyDetails.module.scss'

interface Props {
  text: string
  status: 'thinking' | 'completed' | 'failed'
  completedAt?: string
  durationMs?: number | null
}

export default function ChatReplyDetails({ text, status, completedAt, durationMs }: Props) {
  const [expanded, setExpanded] = useState(status === 'thinking')
  useEffect(() => setExpanded(status === 'thinking'), [status])
  const date = completedAt ? new Date(completedAt) : null
  const validDate = date && Number.isFinite(date.getTime()) ? date : null
  const pad = (value: number) => String(value).padStart(2, '0')
  const timestamp = validDate
    ? `${validDate.getFullYear()}-${pad(validDate.getMonth() + 1)}-${pad(validDate.getDate())} ${pad(validDate.getHours())}:${pad(validDate.getMinutes())}`
    : ''
  const totalSeconds = typeof durationMs === 'number' && Number.isFinite(durationMs) && durationMs >= 0
    ? Math.round(durationMs / 1000) : null
  const duration = totalSeconds !== null
    ? `用时 ${Math.floor(totalSeconds / 60)} 分 ${totalSeconds % 60} 秒` : ''
  return <View className={styles['details'] ?? ''}>
    {text ? <View className={styles['process'] ?? ''}>
      <Button className={styles['toggle'] ?? ''} aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}>
        <Text>{expanded ? '⌄' : '›'} 思考摘要 · {status === 'thinking' ? '正在思考' : status === 'failed' ? '未完成' : '已完成'}</Text>
      </Button>
      {expanded ? <Text className={styles['summary'] ?? ''} selectable>{text}</Text> : null}
    </View> : status === 'failed' ? <Text className={styles['meta'] ?? ''}>本次回答未完成</Text> : null}
    {timestamp || duration ? <Text className={styles['meta'] ?? ''}>{[timestamp, duration].filter(Boolean).join(' · ')}</Text> : null}
  </View>
}
