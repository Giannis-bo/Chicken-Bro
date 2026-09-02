import Taro, { useLoad } from '@tarojs/taro'
import { Button, Text, View } from '@tarojs/components'
import { useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import styles from './web-login-confirm.module.scss'

type ConfirmPagePhase = 'loading' | 'ready' | 'confirming' | 'confirmed' | 'error'

interface ConfirmPageState {
  phase: ConfirmPagePhase
  code: string
  message: string
}

const initialState: ConfirmPageState = {
  phase: 'loading',
  code: '',
  message: '正在准备安全登录…',
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
  const sceneRef = useRef('')
  const accessTokenRef = useRef('')
  const [state, setState] = useState<ConfirmPageState>(initialState)

  const prepareLogin = async (scene: string) => {
    if (!scene) {
      setState({ phase: 'error', code: 'WEB_LOGIN_SCENE_MISSING', message: errorCopy['WEB_LOGIN_SCENE_MISSING'] ?? '链接缺少登录场景。' })
      return
    }
    setState({ phase: 'loading', code: '', message: '正在准备安全登录…' })
    try {
      const login = await Taro.login()
      if (!login.code) {
        setState({ phase: 'error', code: 'MINI_LOGIN_CODE_MISSING', message: '小程序登录未完成，请重试。' })
        return
      }
      const result = await wowApi.webAuth.exchangeMiniCode(login.code)
      if (result.fromFallback || !result.payload.accessToken) {
        setState(resultError(result, '小程序登录未完成，请重试。'))
        return
      }
      accessTokenRef.current = result.payload.accessToken
      setState({ phase: 'ready', code: '', message: '请核对本次 Web 登录，并明确确认。' })
    } catch {
      setState({ phase: 'error', code: 'MINI_LOGIN_FAILED', message: '小程序登录未完成，请重试。' })
    }
  }

  useLoad<{ scene?: string }>((params) => {
    const scene = typeof params.scene === 'string' ? params.scene.trim() : ''
    sceneRef.current = scene
    void prepareLogin(scene)
  })

  const confirmLogin = async () => {
    if (state.phase !== 'ready' || !sceneRef.current || !accessTokenRef.current) return
    setState({ phase: 'confirming', code: '', message: '正在把确认结果交给 Web 页面…' })
    try {
      const result = await wowApi.webAuth.confirmMiniWebLogin(sceneRef.current, accessTokenRef.current)
      if (result.fromFallback) {
        setState(resultError(result, '确认登录失败，请重试。'))
        return
      }
      setState({ phase: 'confirmed', code: '', message: '已确认登录，可以回到 Web 页面继续。' })
    } catch {
      setState({ phase: 'error', code: 'WEB_LOGIN_CONFIRM_FAILED', message: '确认登录失败，请重试。' })
    }
  }

  const retry = () => {
    accessTokenRef.current = ''
    void prepareLogin(sceneRef.current)
  }

  const isBusy = state.phase === 'loading' || state.phase === 'confirming'

  return (
    <View className={styles['page'] ?? ''} data-auth-phase={state.phase}>
      <View className={styles['panel'] ?? ''}>
        <Text className={styles['kicker'] ?? ''}>CHICKENBRO · WEB BRIDGE</Text>
        <Text className={styles['title'] ?? ''}>确认 Web 登录</Text>
        <Text className={styles['description'] ?? ''}>
          这是一次明确的跨设备登录确认。请确认你刚刚在 Web 页面发起了这次操作。
        </Text>

        <View className={styles['statusCard'] ?? ''}>
          <View className={styles['statusDot'] ?? ''} data-status={state.phase} />
          <Text className={styles['statusText'] ?? ''}>{state.message}</Text>
        </View>

        {state.phase === 'ready' || state.phase === 'confirming' ? (
          <Button
            className={styles['confirmAction'] ?? ''}
            disabled={isBusy}
            loading={state.phase === 'confirming'}
            onClick={() => void confirmLogin()}
          >
            确认登录
          </Button>
        ) : null}

        {state.phase === 'confirmed' ? (
          <View className={styles['successCard'] ?? ''}>
            <Text>Web 页面正在等待确认结果。</Text>
            <Text>你可以安全返回刚才的 Web 页面。</Text>
          </View>
        ) : null}

        {state.phase === 'error' ? (
          <Button className={styles['confirmAction'] ?? ''} onClick={retry}>
            重新尝试
          </Button>
        ) : null}

        <Text className={styles['privacyNote'] ?? ''}>本页不会展示账户凭据，也不会自动替你确认登录。</Text>
      </View>
    </View>
  )
}
