import { Button, Text, View } from '@tarojs/components'
import { useRef, useState } from 'react'
import styles from './ChatFeedback.module.scss'
import ChatFeedbackConfirm from './ChatFeedbackConfirm'

interface Props {
  resolved: boolean | null
  onSubmit: (resolved: boolean) => Promise<void>
}

export default function ChatFeedback({ resolved, onSubmit }: Props) {
  const inFlight = useRef(false)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pending, setPending] = useState<boolean | null>(null)
  const submit = async (choice: boolean) => {
    if (inFlight.current || resolved !== null) return
    inFlight.current = true
    setBusy(true)
    setFailed(false)
    try {
      await onSubmit(choice)
    } catch {
      setFailed(true)
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }
  return <View className={styles['feedback'] ?? ''}>
    <View className={styles['choices'] ?? ''}>
      <Text>是否解决</Text>
      {[true, false].map(choice => <Button key={String(choice)}
        className={`${styles['choice'] ?? ''} ${resolved === choice ? styles['selected'] ?? '' : ''}`}
        aria-label={choice ? '已解决' : '未解决'}
        aria-pressed={resolved === choice} disabled={busy || resolved !== null}
        onClick={() => { if (!inFlight.current && resolved === null) setPending(choice) }}>
        <View aria-hidden className={`${styles['icon'] ?? ''} ${choice ? '' : styles['down'] ?? ''}`} />
      </Button>)}
    </View>
    {failed && resolved === null ? <Text className={styles['error'] ?? ''}>反馈未保存，请重试</Text> : null}
    {pending !== null ? <ChatFeedbackConfirm resolved={pending} onCancel={() => setPending(null)}
      onConfirm={() => { setPending(null); void submit(pending) }} /> : null}
  </View>
}
