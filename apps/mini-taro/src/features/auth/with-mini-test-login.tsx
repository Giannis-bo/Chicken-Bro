import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useEffect, useMemo, useState, type ComponentType } from 'react'
import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from './mini-session'
import { isTestLoginEnabled } from './test-login-mode'
import TestLoginForm from './TestLoginForm'
import { MiniHelpActions, MiniHelpContext, MiniHelpPanel, type MiniHelpView } from '../../components/MiniHelp'
import styles from './test-login.module.scss'
import MiniAccountPanel from './MiniAccountPanel'
import { MiniAccountContext } from './mini-account-context'
import { useMiniTheme } from '../theme/use-mini-theme'

export function withMiniTestLogin(Page: ComponentType, hasTab = true) {
  return function MiniTestLoginGate() {
    const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
    const [session, setSession] = useState(() => sessions.getValid())
    const [exiting, setExiting] = useState(false)
    const [signedOut, setSignedOut] = useState(() => sessions.isSignedOut())
    const [accountOpen, setAccountOpen] = useState(false)
    const [loginError, setLoginError] = useState('')
    const [loggingIn, setLoggingIn] = useState(false)
    const { themeStyle } = useMiniTheme()
    const [help, setHelp] = useState<MiniHelpView | null>(null)
    const [keyboardHeight, setKeyboardHeight] = useState(0)
    const [windowHeight] = useState(() => Taro.getWindowInfo?.().windowHeight ?? 0)
    useEffect(() => {
      const update = ({ height }: { height: number }) => setKeyboardHeight(height)
      Taro.onKeyboardHeightChange?.(update)
      return () => { Taro.offKeyboardHeightChange?.(update) }
    }, [])
    const frameStyle = { ...themeStyle, ...(windowHeight ? { height: `${Math.max(160, windowHeight - keyboardHeight)}px` } : {}) }
    const frameClass = `${styles['frame']} ${hasTab && !keyboardHeight ? styles['withTab'] : styles['withoutTab']}`
    useEffect(() => sessions.subscribe(() => { setSession(sessions.getValid()); setSignedOut(sessions.isSignedOut()) }), [sessions])
    useEffect(() => {
      if (!isTestLoginEnabled() || !session) return
      const timer = setTimeout(() => setSession(sessions.getValid()), Math.min(2147483647, Math.max(0, Date.parse(session.expiresAt) - Date.now() + 1)))
      return () => clearTimeout(timer)
    }, [session, sessions])
    useDidShow(() => { setSession(sessions.getValid()); setSignedOut(sessions.isSignedOut()) })
    const testMode = isTestLoginEnabled()
    const needsLogin = (testMode && !session) || signedOut
    const signOut = async () => {
      setAccountOpen(false)
      setHelp(null)
      try { await sessions.signOut() }
      catch { setLoginError('已退出此设备。服务端退出未确认，请稍后重试登录。') }
    }
    const login = async () => {
      if (loggingIn) return
      setLoggingIn(true); setLoginError('')
      try { await sessions.login(true) }
      catch { setLoginError('登录未完成，请重试') }
      finally { setLoggingIn(false) }
    }
    return (
      <MiniAccountContext.Provider value={() => { void Taro.hideKeyboard?.().catch(() => undefined); setAccountOpen(true) }}>
      <MiniHelpContext.Provider value={(view) => {
        void Taro.hideKeyboard?.().catch(() => undefined)
        setHelp(view)
      }}>
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
          <View className={styles[needsLogin ? 'loginBody' : 'body'] ?? ''} style={help || (accountOpen && session && !needsLogin) ? { display: 'none' } : {}}>
            {needsLogin ? <View className={styles['loginHelp'] ?? ''}><MiniHelpActions /></View> : null}
            {needsLogin && !testMode ? <View className={styles['card'] ?? ''}><Text className={styles['title'] ?? ''}>已退出登录</Text><Text className={styles['hint'] ?? ''}>使用当前微信账号重新登录，继续查看聊天与模拟记录。</Text>{loginError ? <Text className={styles['error'] ?? ''}>{loginError}</Text> : null}<Button className={styles['submit'] ?? ''} disabled={loggingIn} onClick={() => void login()}>{loggingIn ? '正在登录…' : '微信登录'}</Button></View> : needsLogin ? <TestLoginForm onLogin={async (account, credential) => {
              const issued = await sessions.loginTestAccount(account, credential)
              setSession(issued)
            }} /> : <Page key={testMode ? session?.accessToken : 'mini'} />}
          </View>
          {accountOpen && session && !needsLogin ? <MiniAccountPanel accessToken={session.accessToken} onClose={() => setAccountOpen(false)} onSignOut={signOut} /> : null}
          {help ? <MiniHelpPanel view={help} onClose={() => setHelp(null)} /> : null}
        </View>
      </MiniHelpContext.Provider>
      </MiniAccountContext.Provider>
    )
  }
}
