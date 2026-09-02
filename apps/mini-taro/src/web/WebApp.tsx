import { Image, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useRef, useState } from 'react'

import type { ApiResult, PrototypeWebClient, WebAuthClient } from '@wow-mini/api-client'
import { wowApi } from '@wow-mini/api-client'
import {
  isMeResponse,
  type MeResponse,
} from '@wow-mini/domain'

import { ActionButton } from '@wow-mini/design-system/components/ActionButton'

import {
  createWebLoginIdempotencyKey,
  getOrCreateBrowserVerifier,
  initialWebAuthState,
  reduceWebAuthState,
  type WebAuthState,
  type WebAuthStateEvent,
} from './web-auth-model'
import PrototypePanel from './PrototypePanel'
import styles from './WebApp.module.scss'

export interface WebAppProps {
  authClient?: WebAuthClient
  prototypeClient?: PrototypeWebClient
}

const problemCopy: Record<string, string> = {
  AUTH_REQUIRED: '当前 Web 会话已失效，请重新扫码登录',
  ORIGIN_REJECTED: '当前页面来源未被允许，请从正式 Web 地址打开',
  WEB_LOGIN_EXPIRED: '二维码已过期，请重新生成',
  WEB_LOGIN_CANCELLED: '小程序已取消这次登录，请重新生成',
  WEB_LOGIN_VERIFIER_MISMATCH: '当前浏览器标签页已变化，请重新生成二维码',
  WEB_LOGIN_ALREADY_EXCHANGED: '这次二维码已经使用过，请重新生成',
  WEB_LOGIN_NOT_CONFIRMED: '请先在小程序中确认登录',
  WECHAT_NOT_CONFIGURED: '登录服务尚未配置完成，请联系管理员',
  WECHAT_PROVIDER_UNAVAILABLE: '微信服务暂不可用，请稍后重试',
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
  const problem = publicProblem(result, '登录状态暂不可用，请重试')
  return { type: 'blocked', ...problem }
}

function phaseLabel(phase: WebAuthState['phase']): string {
  if (phase === 'pending') return '等待小程序扫码'
  if (phase === 'confirmed') return '已扫码，等待你在小程序确认'
  if (phase === 'authenticated') return 'Web 会话已连接'
  if (phase === 'expired') return '二维码已过期'
  if (phase === 'cancelled') return '登录已取消'
  if (phase === 'blocked') return '登录暂不可用'
  return '尚未连接'
}

function remainingSeconds(expiresAt: string, now: number): number {
  if (!expiresAt) return 0
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000))
}

export default function WebApp({ authClient = wowApi.webAuth, prototypeClient = wowApi.prototype }: WebAppProps) {
  const webAuth = authClient
  const [state, setState] = useState<WebAuthState>(initialWebAuthState)
  const stateRef = useRef(state)
  const verifierRef = useRef('')
  const exchangeStartedRef = useRef(false)
  const [account, setAccount] = useState<MeResponse | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [formalLoginVisible, setFormalLoginVisible] = useState(false)

  stateRef.current = state

  const dispatch = (event: WebAuthStateEvent) => {
    setState((current) => reduceWebAuthState(current, event))
  }

  const loadAccount = async () => {
    const result = await webAuth.me()
    if (!result.fromFallback && isMeResponse(result.payload)) {
      setAccount(result.payload)
      dispatch({ type: 'authenticated' })
      return true
    }
    if (isAuthRequired(result)) return false
    const problem = publicProblem(result, '账户状态暂不可用，请稍后重试')
    dispatch({ type: 'blocked', ...problem })
    return false
  }

  useEffect(() => {
    if (!formalLoginVisible) return
    void loadAccount()
    // Formal auth is opt-in from the prototype; the prototype never probes the
    // formal HttpOnly Cookie or renders a signed-out account state.
  }, [formalLoginVisible, webAuth])

  useEffect(() => {
    if (!formalLoginVisible || state.phase !== 'pending' && state.phase !== 'confirmed') return undefined
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [state.phase])

  useEffect(() => {
    if ((state.phase !== 'pending' && state.phase !== 'confirmed') || !state.sessionId || !verifierRef.current) {
      return undefined
    }
    let active = true
    const poll = async () => {
      const result = await webAuth.statusWebLoginSession(state.sessionId, verifierRef.current)
      if (!active) return
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
  }, [formalLoginVisible, webAuth, state.phase, state.sessionId])

  useEffect(() => {
    if (!formalLoginVisible || state.phase !== 'confirmed' || !state.sessionId || !verifierRef.current || exchangeStartedRef.current) return
    exchangeStartedRef.current = true
    const exchange = async () => {
      const result = await webAuth.exchangeWebLoginSession(state.sessionId, verifierRef.current)
      if (result.fromFallback) {
        exchangeStartedRef.current = false
        dispatch({ type: 'blocked', ...publicProblem(result, 'Web 会话建立失败，请重试') })
        return
      }
      const connected = await loadAccount()
      if (!connected) exchangeStartedRef.current = false
    }
    void exchange()
    // The session id and client identify this one exchange attempt.
  }, [formalLoginVisible, webAuth, state.phase, state.sessionId])

  const remaining = useMemo(() => remainingSeconds(state.expiresAt, now), [now, state.expiresAt])

  const createSession = async () => {
    if (stateRef.current.phase === 'pending' || stateRef.current.phase === 'confirmed') return
    exchangeStartedRef.current = false
    setAccount(null)
    dispatch({ type: 'logout' })
    try {
      verifierRef.current = getOrCreateBrowserVerifier()
      const result = await webAuth.createWebLoginSession(
        verifierRef.current,
        createWebLoginIdempotencyKey(),
      )
      if (result.fromFallback) {
        dispatch({ type: 'blocked', ...publicProblem(result, '二维码生成失败，请稍后重试') })
        return
      }
      dispatch({ type: 'created', payload: result.payload })
    } catch (error) {
      dispatch({
        type: 'blocked',
        code: error instanceof Error ? error.message : 'AUTH_REQUEST_FAILED',
        message: problemCopy[error instanceof Error ? error.message : ''] ?? '当前浏览器无法安全保存登录状态',
      })
    }
  }

  const cancelSession = async () => {
    if (!state.sessionId || !verifierRef.current || state.phase !== 'pending' && state.phase !== 'confirmed') return
    const result = await webAuth.cancelWebLoginSession(state.sessionId, verifierRef.current)
    if (result.fromFallback) {
      dispatch({ type: 'blocked', ...publicProblem(result, '取消登录失败，请稍后重试') })
      return
    }
    dispatch({ type: 'status', payload: result.payload })
  }

  const logout = async () => {
    const result = await webAuth.logout()
    setAccount(null)
    exchangeStartedRef.current = false
    if (result.fromFallback) {
      dispatch({ type: 'blocked', ...publicProblem(result, '退出登录失败，请稍后重试') })
      return
    }
    dispatch({ type: 'logout' })
  }

  const phase = state.phase
  const activeQr = phase === 'pending' || phase === 'confirmed'
  const terminalAction = phase === 'expired' || phase === 'cancelled' || phase === 'blocked'

  if (!formalLoginVisible) {
    return (
      <PrototypePanel
        client={prototypeClient}
        onOpenFormalLogin={() => setFormalLoginVisible(true)}
      />
    )
  }

  return (
    <View className={styles['page'] ?? ''} data-auth-phase={phase} data-auth-transport="credentials-include">
      <View className={styles['backdrop'] ?? ''} />
      <View className={styles['shell'] ?? ''}>
        <View className={styles['topbar'] ?? ''}>
          <View className={styles['brandRow'] ?? ''}>
            <View className={styles['brandMark'] ?? ''}>CB</View>
            <View>
              <Text className={styles['brandName'] ?? ''}>CHICKENBRO</Text>
              <Text className={styles['brandMeta'] ?? ''}>WEB ACCESS · PRIVATE BUILD DESK</Text>
            </View>
          </View>
          <ActionButton
            className={styles['secondaryAction'] ?? ''}
            variant="secondaryMetal"
            onClick={() => setFormalLoginVisible(false)}
          >
            返回 Web 原型
          </ActionButton>
        </View>

        <View className={styles['content'] ?? ''}>
          <View className={styles['hero'] ?? ''}>
            <Text className={styles['eyebrow'] ?? ''}>装备事实 · 模拟边界 · 账户连接</Text>
            <Text className={styles['title'] ?? ''}>把小程序里的战备工作，安全地带到 Web。</Text>
            <Text className={styles['lede'] ?? ''}>
              使用同一个微信账户连接你的装备、天赋与模拟工作台；Web 只接收独立会话，不读取小程序登录凭据。
            </Text>
            <View className={styles['trustLine'] ?? ''}>
              <View className={styles['trustDot'] ?? ''} />
              <Text>同源安全会话 · 小程序明确确认 · 不在二维码中暴露身份</Text>
            </View>
          </View>

          <View className={styles['loginCard'] ?? ''} data-card="wechat-login">
            <View className={styles['cardTopline'] ?? ''}>
              <Text className={styles['cardKicker'] ?? ''}>WECHAT BRIDGE</Text>
              <Text className={styles['cardState'] ?? ''}>{phaseLabel(phase)}</Text>
            </View>

            {phase === 'idle' ? (
              <View className={styles['idlePanel'] ?? ''}>
                <View className={styles['wechatGlyph'] ?? ''}>微</View>
                <Text className={styles['cardTitle'] ?? ''}>使用微信小程序登录</Text>
                <Text className={styles['cardDescription'] ?? ''}>
                  点击后生成一次性二维码。请用 Chickenbro 小程序扫描，并在小程序内明确点击确认登录。
                </Text>
                <ActionButton className={styles['primaryAction'] ?? ''} block variant="primaryGold" onClick={() => void createSession()}>
                  使用微信小程序登录
                </ActionButton>
                <Text className={styles['smallPrint'] ?? ''}>请使用电脑或另一台设备展示二维码</Text>
              </View>
            ) : null}

            {activeQr ? (
              <View className={styles['qrPanel'] ?? ''}>
                <View className={styles['qrFrame'] ?? ''}>
                  <Image className={styles['qrImage'] ?? ''} src={state.qrDataUrl} mode="aspectFit" />
                </View>
                <Text className={styles['qrTitle'] ?? ''}>
                  {phase === 'confirmed' ? '登录已确认，正在建立 Web 会话' : '请用微信小程序扫描二维码'}
                </Text>
                <Text className={styles['qrInstruction'] ?? ''}>
                  扫码后请回到小程序，核对页面与设备，使用小程序确认登录。
                </Text>
                <Text className={styles['countdown'] ?? ''}>
                  {remaining > 0 ? `二维码剩余 ${remaining} 秒` : '二维码已过期'}
                </Text>
                <View className={styles['actionRow'] ?? ''}>
                  <ActionButton className={styles['secondaryAction'] ?? ''} variant="secondaryMetal" onClick={() => void cancelSession()}>
                    取消登录
                  </ActionButton>
                  {remaining === 0 ? (
                    <ActionButton className={styles['primaryAction'] ?? ''} variant="primaryGold" onClick={() => void createSession()}>
                      重新生成
                    </ActionButton>
                  ) : null}
                </View>
              </View>
            ) : null}

            {phase === 'authenticated' ? (
              <View className={styles['connectedPanel'] ?? ''}>
                <View className={styles['connectedBadge'] ?? ''}>已连接</View>
                <Text className={styles['cardTitle'] ?? ''}>{account?.displayName || '微信账户'}</Text>
                <Text className={styles['cardDescription'] ?? ''}>Web 会话已建立。后续页面会继续沿用这个 HttpOnly Cookie。</Text>
                <View className={styles['nextStageGrid'] ?? ''}>
                  <View className={styles['nextStageCard'] ?? ''} data-disabled="true">
                    <Text className={styles['nextStageLabel'] ?? ''}>队长</Text>
                    <Text>下一阶段 · 构筑工作台</Text>
                  </View>
                  <View className={styles['nextStageCard'] ?? ''} data-disabled="true">
                    <Text className={styles['nextStageLabel'] ?? ''}>SimC</Text>
                    <Text>下一阶段 · 模拟任务</Text>
                  </View>
                </View>
                <ActionButton className={styles['secondaryAction'] ?? ''} block variant="secondaryMetal" onClick={() => void logout()}>
                  退出 Web 登录
                </ActionButton>
              </View>
            ) : null}

            {terminalAction ? (
              <View className={styles['blockedPanel'] ?? ''} data-state="blocked-or-terminal">
                <Text className={styles['cardTitle'] ?? ''}>{phaseLabel(phase)}</Text>
                <Text className={styles['cardDescription'] ?? ''}>{state.errorMessage || problemCopy[state.errorCode] || '这次登录没有完成，当前没有建立 Web 会话。'}</Text>
                <ActionButton className={styles['primaryAction'] ?? ''} block variant="primaryGold" onClick={() => void createSession()}>
                  重新生成二维码
                </ActionButton>
              </View>
            ) : null}
          </View>

          <View className={styles['footerNote'] ?? ''}>
            <Text>Web 与小程序使用不同会话边界；只有同一个内部账户 ID 用于关联你的资料。</Text>
            <Text>本页面是登录原型，未登录时不会伪造账户或展示业务数据。</Text>
          </View>
        </View>
      </View>
    </View>
  )
}
