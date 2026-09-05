import { useEffect, useState } from 'react'

import styles from './WebApp.module.scss'

/** Request waiting only: the stream does not expose internal reasoning stages. */
export default function WebReplyStatus() {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className={styles['webAssistantMessage'] ?? ''} data-persisted="false">
      <div className={styles['messageRole'] ?? ''}>咕咕</div>
      <div className={styles['replyWaiting'] ?? ''} role="status" aria-label="等待回复" aria-live="polite">
        <span className={styles['replyDots'] ?? ''} aria-hidden="true">
          <span /><span /><span />
        </span>
        <span>咕咕正在处理…</span>
        {seconds >= 10 ? (
          <span className={styles['replyElapsed'] ?? ''} aria-hidden="true">已等待 {seconds} 秒</span>
        ) : null}
      </div>
    </div>
  )
}
