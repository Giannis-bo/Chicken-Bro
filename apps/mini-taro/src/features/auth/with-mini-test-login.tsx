import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useEffect, useMemo, useState, type ComponentType } from 'react'
import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from './mini-session'
import { isTestLoginEnabled } from './test-login-mode'
import TestLoginForm from './TestLoginForm'
import { MiniHelpActions, MiniHelpPanel, type MiniHelpView } from '../../components/MiniHelp'
import styles from './test-login.module.scss'

export function withMiniTestLogin(Page: ComponentType, hasTab = true) {
  return function MiniTestLoginGate() {
    const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
    const [session, setSession] = useState(() => sessions.getValid())
    const [exiting, setExiting] = useState(false)
    const [help, setHelp] = useState<MiniHelpView | null>(null)
    const [keyboardHeight, setKeyboardHeight] = useState(0)
    const [windowHeight] = useState(() => Taro.getWindowInfo?.().windowHeight ?? 0)
    useEffect(() => {
      const update = ({ height }: { height: number }) => setKeyboardHeight(height)
      Taro.onKeyboardHeightChange?.(update)
      return () => { Taro.offKeyboardHeightChange?.(update) }
    }, [])
    const frameStyle = windowHeight ? { height: `${Math.max(160, windowHeight - keyboardHeight)}px` } : {}
    const frameClass = `${styles['frame']} ${hasTab && !keyboardHeight ? styles['withTab'] : styles['withoutTab']}`
    useEffect(() => sessions.subscribe(() => setSession(sessions.getValid())), [sessions])
    useEffect(() => {
      if (!isTestLoginEnabled() || !session) return
      const timer = setTimeout(() => setSession(sessions.getValid()), Math.min(2147483647, Math.max(0, Date.parse(session.expiresAt) - Date.now() + 1)))
      return () => clearTimeout(timer)
    }, [session, sessions])
    useDidShow(() => setSession(sessions.getValid()))
    const testMode = isTestLoginEnabled()
    const needsLogin = testMode && !session
    return (
      <View className={frameClass} style={frameStyle}>
        {testMode && session ? <View className={styles['banner'] ?? ''}>
          <Text>测试环境 · 真实业务</Text>
          <Button size="mini" disabled={exiting} onClick={() => {
            if (exiting) return
            setExiting(true)
            void sessions.logout().catch(() => undefined).finally(() => {
              setSession(null)
              setExiting(false)
            })
          }}>退出 / 切换账号</Button>
        </View> : null}
        <MiniHelpActions active={help} onOpen={(view) => {
          void Taro.hideKeyboard?.().catch(() => undefined)
          setHelp(view)
        }} />
        <View className={styles[needsLogin ? 'loginBody' : 'body'] ?? ''} style={help ? { display: 'none' } : {}}>
          {needsLogin ? <TestLoginForm onLogin={async (account, credential) => {
            const issued = await sessions.loginTestAccount(account, credential)
            setSession(issued)
          }} /> : <Page key={testMode ? session?.accessToken : 'mini'} />}
        </View>
        {help ? <MiniHelpPanel view={help} onClose={() => setHelp(null)} /> : null}
      </View>
    )
  }
}
