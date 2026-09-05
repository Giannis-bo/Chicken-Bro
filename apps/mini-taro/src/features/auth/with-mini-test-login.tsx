import { Button, Text, View } from '@tarojs/components'
import { useDidShow } from '@tarojs/taro'
import { useEffect, useMemo, useState, type ComponentType } from 'react'
import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from './mini-session'
import { isTestLoginEnabled } from './test-login-mode'
import TestLoginForm from './TestLoginForm'
import styles from './test-login.module.scss'

export function withMiniTestLogin(Page: ComponentType) {
  return function MiniTestLoginGate() {
    const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
    const [session, setSession] = useState(() => sessions.getValid())
    const [exiting, setExiting] = useState(false)
    useEffect(() => sessions.subscribe(() => setSession(sessions.getValid())), [sessions])
    useEffect(() => {
      if (!isTestLoginEnabled() || !session) return
      const timer = setTimeout(() => setSession(sessions.getValid()), Math.min(2147483647, Math.max(0, Date.parse(session.expiresAt) - Date.now() + 1)))
      return () => clearTimeout(timer)
    }, [session, sessions])
    useDidShow(() => setSession(sessions.getValid()))
    if (!isTestLoginEnabled()) return <Page />
    if (!session) {
      return <TestLoginForm onLogin={async (account, credential) => {
        const issued = await sessions.loginTestAccount(account, credential)
        setSession(issued)
      }} />
    }
    return (
      <View>
        <View className={styles['banner'] ?? ''}>
          <Text>测试环境 · 真实业务</Text>
          <Button size="mini" disabled={exiting} onClick={() => {
            if (exiting) return
            setExiting(true)
            void sessions.logout().catch(() => undefined).finally(() => {
              setSession(null)
              setExiting(false)
            })
          }}>退出 / 切换账号</Button>
        </View>
        <Page key={session.accessToken} />
      </View>
    )
  }
}
