import { useEffect, useState } from 'react'
import { apiV2Path, wowApi } from '@wow-mini/api-client'

import styles from './WebApp.module.scss'

type Health = 'checking' | 'ready' | 'partial' | 'blocked' | 'unavailable'
const labels: Record<Health, string> = {
  checking: '正在检查服务', ready: '服务正常', partial: '部分服务不可用',
  blocked: '服务不可用', unavailable: '服务连接异常',
}

export default function WebServiceHealth() {
  const [health, setHealth] = useState<Health>('checking')
  useEffect(() => {
    let disposed = false
    let pending = false
    const check = async () => {
      if (pending || document.visibilityState === 'hidden') return
      pending = true
      try {
        const result = await wowApi.transport.request<{ status?: string }>(apiV2Path('/health/readiness'), {
          auth: { kind: 'public' }, baseUrl: 'web-auth', timeoutMs: 8000,
          fallback: () => ({}),
        })
        const status = result.payload?.status
        if (!disposed) setHealth(!result.fromFallback && (status === 'ready' || status === 'partial' || status === 'blocked')
          ? status : 'unavailable')
      } catch {
        if (!disposed) setHealth('unavailable')
      } finally {
        pending = false
      }
    }
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        setHealth('checking')
        void check()
      }
    }
    void check()
    const timer = window.setInterval(() => void check(), 60_000)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      disposed = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <span className={styles['serviceHealth'] ?? ''} data-health={health}
    role="status" aria-label={labels[health]} title={labels[health]} />
}
