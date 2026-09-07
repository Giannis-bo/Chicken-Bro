import Taro, { useLoad } from '@tarojs/taro'
import { Button, Image, Text, View } from '@tarojs/components'
import { useMemo, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import styles from './web-login-confirm.module.scss'
import mascot from '../../web/assets/gu-gu-mascot.png'
import { MiniSessionStore } from '../../features/auth/mini-session'

type ConfirmPagePhase = 'loading' | 'ready' | 'confirming' | 'confirmed' | 'error'

interface ConfirmPageState {
  phase: ConfirmPagePhase
  code: string
  message: string
}

const initialState: ConfirmPageState = {
  phase: 'loading',
  code: '',
  message: '正在准备登录…',
}

const errorCopy: Record<string, string> = {
  WEB_LOGIN_SCENE_MISSING: '链接缺少登录场景，请回到 Web 页面重新生成二维码。',
  AUTH_REQUIRED: '小程序登录已失效，请重新打开此确认页。',
  WEB_LOGIN_EXPIRED: '二维码已过期，请回到 Web 页面重新生成。',
  WEB_LOGIN_CANCELLED: '这次登录已取消，请回到 Web 页面重新生成。',
  WEB_LOGIN_ALREADY_CONSUMED: '这次登录已完成，请回到 Web 页面查看结果。',
  WEB_LOGIN_NOT_FOUND: '登录场景不存在，请回到 Web 页面重新生成。',
  WECHAT_PROVIDER_UNAVAILABLE: '微信服务暂不可用，请稍后重试。',
  WECHAT_NOT_CONFIGURED: '登录服务尚未配置完成，请联系管理员。',
}

function resultError(result: { problemCode?: string; error: string }, fallback: string): ConfirmPageState {
  const code = result.problemCode ?? 'AUTH_REQUEST_FAILED'
  return {
    phase: 'error',
    code,
    message: errorCopy[code] ?? (result.error || fallback),
  }
}

export default function WebLoginConfirmPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const confirmingRef = useRef(false)
  const navigatingRef = useRef(false)
  const [navigationFailed, setNavigationFailed] = useState(false)
  const sceneRef = useRef('')
  const accessTokenRef = useRef('')
  const [state, setState] = useState<ConfirmPageState>(initialState)

  const prepareLogin = async (scene: string) => {
    if (!scene) {
      setState({ phase: 'error', code: 'WEB_LOGIN_SCENE_MISSING', message: errorCopy['WEB_LOGIN_SCENE_MISSING'] ?? '链接缺少登录场景。' })
      return
    }
    setState({ phase: 'loading', code: '', message: '正在准备登录…' })
    try {
      const session = await sessions.login()
      accessTokenRef.current = session.accessToken
      setState({ phase: 'ready', code: '', message: '鸡哥已就位，等你开聊。' })
    } catch (error) {
      const code = error instanceof Error ? error.message : 'MINI_LOGIN_FAILED'
      setState({ phase: 'error', code, message: errorCopy[code] ?? '小程序登录未完成，请重试。' })
    }
  }

  useLoad<{ scene?: string }>((params) => {
    const scene = typeof params.scene === 'string' ? params.scene.trim() : ''
    sceneRef.current = scene
    void prepareLogin(scene)
  })

  const enterMini = async () => {
    if (navigatingRef.current) return
    navigatingRef.current = true
    setNavigationFailed(false)
    try {
      await Taro.switchTab({ url: '/pages/chickenbro/index' })
    } catch {
      setNavigationFailed(true)
      setState({ phase: 'confirmed', code: '', message: '登录成功，点击进入小程序。' })
    } finally {
      navigatingRef.current = false
    }
  }

  const confirmLogin = async () => {
    if (confirmingRef.current || state.phase !== 'ready' || !sceneRef.current || !accessTokenRef.current) return
    confirmingRef.current = true
    setState({ phase: 'confirming', code: '', message: '正在登录…' })
    try {
      const result = await wowApi.webAuth.confirmMiniWebLogin(sceneRef.current, accessTokenRef.current)
      if (result.fromFallback) {
        setState(resultError(result, '确认登录失败，请重试。'))
        return
      }
      setState({ phase: 'confirmed', code: '', message: '正在进入小程序…' })
      await enterMini()
    } catch {
      setState({ phase: 'error', code: 'WEB_LOGIN_CONFIRM_FAILED', message: '确认登录失败，请重试。' })
    } finally {
      confirmingRef.current = false
    }
  }

  const retry = () => {
    accessTokenRef.current = ''
    void prepareLogin(sceneRef.current)
  }

  const isBusy = state.phase === 'loading' || state.phase === 'confirming'

  return (
    <View className={styles['page'] ?? ''} data-auth-phase={state.phase}>
      <View className={styles['brand'] ?? ''}>
        <Image className={styles['mascot'] ?? ''} src={mascot} mode="aspectFit" />
        <Text className={styles['brandName'] ?? ''}>炸鸡队长来啦</Text>
        <Text className={styles['brandNote'] ?? ''}>CHICKENBRO</Text>
      </View>
      <View className={styles['panel'] ?? ''}>
        <Text className={styles['title'] ?? ''}>{state.phase === 'confirmed' ? '登录成功' : '登录网页版'}</Text>
        <Text className={`${styles['status'] ?? ''} ${state.phase === 'error' ? styles['error'] ?? '' : ''}`}>{state.message}</Text>
        {state.phase === 'ready' || state.phase === 'confirming' ? (
          <Button className={styles['confirmAction'] ?? ''} disabled={isBusy}
            loading={state.phase === 'confirming'} onClick={() => void confirmLogin()}>
            确认登录
          </Button>
        ) : null}
        {state.phase === 'confirmed' && navigationFailed ? (
          <Button className={styles['confirmAction'] ?? ''} onClick={() => void enterMini()}>进入小程序</Button>
        ) : null}
        {state.phase === 'confirmed' ? <View className={styles['success'] ?? ''}>✓</View> : null}
        {state.phase === 'error' ? (
          <Button className={styles['confirmAction'] ?? ''} onClick={retry}>重新尝试</Button>
        ) : null}
      </View>
    </View>
  )
}
