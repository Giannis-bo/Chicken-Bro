import TestLoginForm from '../features/auth/TestLoginForm'
import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import { Button, Image, Text, View } from '@tarojs/components'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  readWebCsrfCookie,
  type ApiResult,
  type ClientAuthContext,
  type WebAuthClient,
} from '@wow-mini/api-client'
import { wowApi } from '@wow-mini/api-client'
import { isMeResponse, type MeResponse } from '@wow-mini/domain'

import WebShell from './WebShell'
import {
  getOrCreateBrowserVerifier,
  initialWebAuthState,
  reduceWebAuthState,
  selectWebLoginCreateAttempt,
  shouldDiscardWebLoginCreateAttempt,
  WebAuthIntentFence,
  type WebLoginCreateAttempt,
  type WebAuthState,
  type WebAuthStateEvent,
} from './web-auth-model'
import styles from './WebApp.module.scss'


export interface WebAppProps {
  authClient?: WebAuthClient
}

type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>

const problemCopy: Record<string, string> = {
  AUTH_REQUIRED: '当前 Web 会话已失效，请重新扫码登录',
  ORIGIN_REJECTED: '当前页面来源未被允许，请从正式 Web 地址打开',
  WEB_LOGIN_EXPIRED: '二维码已过期，请重新生成',
  WEB_LOGIN_CANCELLED: '小程序已取消这次登录，请重新生成',
  WEB_LOGIN_VERIFIER_MISMATCH: '当前浏览器标签页已变化，请重新生成二维码',
  WEB_LOGIN_ALREADY_CONSUMED: '这次二维码已经使用过，请重新生成',
  WEB_LOGIN_NOT_CONFIRMED: '请先在小程序中确认登录',
  WEB_LOGIN_RESTART_REQUIRED: '上一次二维码已失效，请重新生成',
  WECHAT_NOT_CONFIGURED: '登录服务尚未配置完成，请联系管理员',
  WECHAT_PROVIDER_UNAVAILABLE: '微信服务暂不可用，请稍后重试',
  WEB_CSRF_COOKIE_MISSING: 'Web 安全会话不完整，请重新扫码登录',
  WEB_CSRF_COOKIE_INVALID: 'Web 安全会话无效，请重新扫码登录',
  AUTH_REQUEST_FAILED: '登录服务暂不可用，请稍后重试',
  INVALID_QR_RESPONSE: '登录二维码无效，请重新生成',
}

function publicProblem(result: ApiResult<unknown>, fallback: string): { code: string; message: string } {
  const code = result.problemCode ?? ''
  return {
    code: code || 'AUTH_REQUEST_FAILED',
    message: problemCopy[code] ?? (result.error || fallback),
  }
}

function isAuthRequired(result: ApiResult<unknown>): boolean {
  return result.httpStatus === 401 || result.problemCode === 'AUTH_REQUIRED'
}

function statusFailureEvent(result: ApiResult<unknown>): WebAuthStateEvent {
  if (result.httpStatus === 410 || result.problemCode === 'WEB_LOGIN_EXPIRED') {
    return { type: 'status', payload: { status: 'expired', expiresAt: new Date().toISOString() } }
  }
  if (result.httpStatus === 409 && result.problemCode === 'WEB_LOGIN_CANCELLED') {
    return { type: 'status', payload: { status: 'cancelled', expiresAt: new Date().toISOString() } }
  }
  return { type: 'blocked', ...publicProblem(result, '登录状态暂不可用，请重试') }
}

function phaseLabel(phase: WebAuthState['phase']): string {
  if (phase === 'checking') return '正在检查 Web 会话'
  if (phase === 'signed_out') return '等待连接微信账户'
  if (phase === 'qr_pending') return '等待小程序扫码'
  if (phase === 'qr_confirmed') return '小程序已确认'
  if (phase === 'authenticated') return 'Web 会话已连接'
  return '登录暂不可用'
}

function remainingSeconds(expiresAt: string, now: number): number {
  if (!expiresAt) return 0
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000))
}

export default function WebApp({ authClient = wowApi.webAuth }: WebAppProps) {
  const webAuth = authClient
  const [state, setState] = useState<WebAuthState>(initialWebAuthState)
  const [account, setAccount] = useState<MeResponse | null>(null)
  const [authContext, setAuthContext] = useState<WebClientAuth | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const stateRef = useRef(state)
  const verifierRef = useRef('')
  const exchangeStartedRef = useRef(false)
  const createAttemptRef = useRef<WebLoginCreateAttempt | null>(null)
  const createInFlightRef = useRef(false)
  const authIntentRef = useRef(new WebAuthIntentFence())
  stateRef.current = state

  const dispatch = useCallback((event: WebAuthStateEvent) => {
    setState((current) => reduceWebAuthState(current, event))
  }, [])

  const loadAccount = useCallback(async (existingIntent?: number): Promise<boolean> => {
    const intent = existingIntent ?? authIntentRef.current.begin()
    if (!authIntentRef.current.isCurrent(intent)) return false
    const result = await webAuth.me()
    if (!authIntentRef.current.isCurrent(intent)) return false
    if (!result.fromFallback && isMeResponse(result.payload)) {
      try {
        const csrfToken = readWebCsrfCookie()
        setAccount(result.payload)
        setAuthContext({ kind: 'web', csrfToken })
        dispatch({ type: 'authenticated' })
        return true
      } catch (error) {
        const code = error instanceof Error ? error.message : 'WEB_CSRF_COOKIE_INVALID'
        dispatch({
          type: 'blocked',
          code,
          message: problemCopy[code] ?? 'Web 安全会话无效，请重新扫码登录',
        })
        return false
      }
    }
    setAccount(null)
    setAuthContext(null)
    if (isAuthRequired(result)) {
      dispatch({
        type: 'signed_out',
        code: 'AUTH_REQUIRED',
        message: problemCopy['AUTH_REQUIRED'] ?? '当前 Web 会话已失效，请重新扫码登录',
      })
      return false
    }
    dispatch({ type: 'blocked', ...publicProblem(result, '账户状态暂不可用，请稍后重试') })
    return false
  }, [dispatch, webAuth])

  useEffect(() => () => authIntentRef.current.invalidate(), [])

  useEffect(() => {
    if (state.phase !== 'checking') return
    void loadAccount()
  }, [loadAccount, state.phase])

  useEffect(() => {
    if (state.phase !== 'qr_pending' && state.phase !== 'qr_confirmed') return undefined
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [state.phase])

  useEffect(() => {
    if (
      state.phase !== 'qr_pending'
      || !state.sessionId
      || !verifierRef.current
    ) return undefined
    let active = true
    const intent = authIntentRef.current.capture()
    const poll = async () => {
      const result = await webAuth.statusWebLoginSession(state.sessionId, verifierRef.current)
      if (!active || !authIntentRef.current.isCurrent(intent)) return
      if (result.fromFallback) {
        dispatch(statusFailureEvent(result))
        return
      }
      dispatch({ type: 'status', payload: result.payload })
    }
    void poll()
    const timer = setInterval(() => { void poll() }, 1500)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [dispatch, state.phase, state.sessionId, webAuth])

  useEffect(() => {
    if (
      state.phase !== 'qr_confirmed'
      || !state.sessionId
      || !verifierRef.current
      || exchangeStartedRef.current
    ) return
    exchangeStartedRef.current = true
    const intent = authIntentRef.current.capture()
    const exchange = async () => {
      const result = await webAuth.exchangeWebLoginSession(state.sessionId, verifierRef.current)
      if (!authIntentRef.current.isCurrent(intent)) return
      if (result.fromFallback) {
        exchangeStartedRef.current = false
        dispatch({ type: 'blocked', ...publicProblem(result, 'Web 会话建立失败，请重试') })
        return
      }
      const connected = await loadAccount(intent)
      if (!connected && authIntentRef.current.isCurrent(intent)) {
        exchangeStartedRef.current = false
      }
    }
    void exchange()
  }, [dispatch, loadAccount, state.phase, state.sessionId, webAuth])

  const remaining = useMemo(
    () => remainingSeconds(state.expiresAt, now),
    [now, state.expiresAt],
  )

  const createSession = async (replaceActive = false) => {
    if (createInFlightRef.current) return
    if (
      !replaceActive
      && (stateRef.current.phase === 'qr_pending' || stateRef.current.phase === 'qr_confirmed')
    ) return
    const intent = authIntentRef.current.begin()
    exchangeStartedRef.current = false
    setAccount(null)
    setAuthContext(null)
    dispatch({ type: 'signed_out' })
    createInFlightRef.current = true
    try {
      const browserVerifier = getOrCreateBrowserVerifier()
      verifierRef.current = browserVerifier
      const attempt = selectWebLoginCreateAttempt(
        createAttemptRef.current,
        browserVerifier,
        replaceActive,
      )
      createAttemptRef.current = attempt
      const result = await webAuth.createWebLoginSession(
        attempt.browserVerifier,
        attempt.idempotencyKey,
      )
      if (!authIntentRef.current.isCurrent(intent)) {
        if (createAttemptRef.current === attempt) createAttemptRef.current = null
        return
      }
      if (result.fromFallback) {
        if (
          shouldDiscardWebLoginCreateAttempt(result.problemCode)
          && createAttemptRef.current === attempt
        ) createAttemptRef.current = null
        dispatch({ type: 'blocked', ...publicProblem(result, '二维码生成失败，请稍后重试') })
        return
      }
      if (createAttemptRef.current === attempt) createAttemptRef.current = null
      dispatch({ type: 'created', payload: result.payload })
    } catch (error) {
      if (!authIntentRef.current.isCurrent(intent)) return
      const code = error instanceof Error ? error.message : 'AUTH_REQUEST_FAILED'
      dispatch({
        type: 'blocked',
        code,
        message: problemCopy[code] ?? '当前浏览器无法安全保存登录状态',
      })
    } finally {
      createInFlightRef.current = false
    }
  }

  const cancelSession = async () => {
    if (
      !state.sessionId
      || !verifierRef.current
      || (state.phase !== 'qr_pending' && state.phase !== 'qr_confirmed')
    ) return
    const intent = authIntentRef.current.begin()
    const result = await webAuth.cancelWebLoginSession(state.sessionId, verifierRef.current)
    if (!authIntentRef.current.isCurrent(intent)) return
    if (result.fromFallback) {
      dispatch({ type: 'blocked', ...publicProblem(result, '取消登录失败，请稍后重试') })
      return
    }
    dispatch({ type: 'status', payload: result.payload })
  }

  const logout = async () => {
    const intent = authIntentRef.current.begin()
    if (!authContext) {
      dispatch({ type: 'logout' })
      return
    }
    const result = await webAuth.logout(authContext)
    if (!authIntentRef.current.isCurrent(intent)) return
    if (result.fromFallback) {
      dispatch({ type: 'blocked', ...publicProblem(result, '退出登录失败，请稍后重试') })
      return
    }
    setAccount(null)
    setAuthContext(null)
    exchangeStartedRef.current = false
    dispatch({ type: 'logout' })
  }

  if (state.phase === 'authenticated' && account && authContext) {
    return (
      <WebShell
        accountLabel={account.displayName || '微信账户'}
        auth={authContext}
        onLogout={() => void logout()}
      />
    )
  }

  if (isTestLoginEnabled() && state.phase !== 'checking') {
    return <TestLoginForm onLogin={async (testAccount, credential) => {
      const intent = authIntentRef.current.begin()
      const result = await webAuth.loginTestWeb(testAccount, credential)
      if (!authIntentRef.current.isCurrent(intent)) return
      if (result.fromFallback) throw new Error(result.problemCode || 'TEST_LOGIN_FAILED')
      if (!await loadAccount(intent)) throw new Error('TEST_LOGIN_FAILED')
    }} />
  }

  const activeQr = state.phase === 'qr_pending' || state.phase === 'qr_confirmed'

  return (
    <View className={styles['page'] ?? ''} data-auth-phase={state.phase} data-auth-transport="credentials-include">
      <View className={styles['loginShell'] ?? ''}>
        <View className={styles['brand'] ?? ''}>
          <View className={styles['brandMascotFrame'] ?? ''}>
            <View className={styles['brandMascot'] ?? ''} />
          </View>
          <View className={styles['brandCopy'] ?? ''}>
            <Text className={styles['brandName'] ?? ''}>炸鸡队长来啦</Text>
            <Text className={styles['brandMeta'] ?? ''}>WOW COMPANION · WEB</Text>
          </View>
        </View>

        <View className={styles['loginCard'] ?? ''}>
          <Text className={styles['cardKicker'] ?? ''}>{phaseLabel(state.phase)}</Text>

          {state.phase === 'checking' ? (
            <View className={styles['statePanel'] ?? ''}>
              <Text className={styles['cardTitle'] ?? ''}>正在检查 Web 会话</Text>
              <Text className={styles['cardDescription'] ?? ''}>已登录时会直接恢复你的服务端会话与 SimC 历史。</Text>
            </View>
          ) : null}

          {state.phase === 'signed_out' ? (
            <View className={styles['statePanel'] ?? ''}>
              <View className={styles['wechatGlyph'] ?? ''}>微</View>
              <Text className={styles['cardTitle'] ?? ''}>使用微信小程序登录</Text>
              <Text className={styles['cardDescription'] ?? ''}>
                Web 不读取小程序 token。扫码后请在小程序中明确使用小程序确认，浏览器只获得独立的安全 Cookie。
              </Text>
              {state.errorMessage ? <Text className={styles['notice'] ?? ''}>{state.errorMessage}</Text> : null}
              <Button className={styles['primaryButton'] ?? ''} onClick={() => void createSession()}>
                使用微信小程序登录
              </Button>
              <Text className={styles['smallPrint'] ?? ''}>请使用电脑或另一台设备展示二维码</Text>
            </View>
          ) : null}

          {activeQr ? (
            <View className={styles['statePanel'] ?? ''}>
              <View className={styles['qrFrame'] ?? ''}>
                <Image className={styles['qrImage'] ?? ''} src={state.qrDataUrl} mode="aspectFit" />
              </View>
              <Text className={styles['cardTitle'] ?? ''}>
                {state.phase === 'qr_confirmed'
                  ? '登录已确认，正在建立 Web 会话'
                  : '请用微信小程序扫描二维码'}
              </Text>
              <Text className={styles['cardDescription'] ?? ''}>
                扫码后回到小程序核对本次操作，并明确使用小程序确认。
              </Text>
              <Text className={styles['countdown'] ?? ''}>
                {remaining > 0 ? `二维码剩余 ${remaining} 秒` : '二维码已过期'}
              </Text>
              <View className={styles['actionRow'] ?? ''}>
                <Button className={styles['secondaryButton'] ?? ''} onClick={() => void cancelSession()}>
                  取消登录
                </Button>
                {remaining === 0 ? (
                  <Button className={styles['primaryButton'] ?? ''} onClick={() => void createSession(true)}>
                    重新生成
                  </Button>
                ) : null}
              </View>
            </View>
          ) : null}

          {state.phase === 'blocked' ? (
            <View className={styles['statePanel'] ?? ''} data-error-code={state.errorCode}>
              <Text className={styles['cardTitle'] ?? ''}>登录暂不可用</Text>
              <Text className={styles['notice'] ?? ''}>{state.errorMessage || problemCopy[state.errorCode]}</Text>
              <View className={styles['actionRow'] ?? ''}>
                <Button className={styles['secondaryButton'] ?? ''} onClick={() => void loadAccount()}>
                  重新检查
                </Button>
                <Button className={styles['primaryButton'] ?? ''} onClick={() => void createSession()}>
                  重新扫码
                </Button>
              </View>
            </View>
          ) : null}
        </View>

        <Text className={styles['trustNote'] ?? ''}>
          Web Cookie 与 Mini Bearer 相互独立；共享的只有同一内部用户及其服务端 Chat / SimC 历史。
        </Text>
      </View>
    </View>
  )
}
