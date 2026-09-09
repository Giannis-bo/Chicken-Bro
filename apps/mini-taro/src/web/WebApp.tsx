import TestLoginForm from '../features/auth/TestLoginForm'
import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import { useCallback, useEffect, useRef, useState } from 'react'
import { readWebCsrfCookie, wowApi, type ApiResult, type ClientAuthContext, type WebAuthClient } from '@wow-mini/api-client'
import { isMeResponse, isQqLoginCreated, type MeResponse } from '@wow-mini/domain'
import { normalizeWebUrl } from './web-routing'
import WebShell from './WebShell'
import WebLoginHome from './WebLoginHome'
import { readAndClearLoginError } from './web-auth-model'
import styles from './WebLoginCard.module.scss'

type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>
type AuthPhase = 'checking' | 'signed_out' | 'redirecting' | 'authenticated' | 'blocked'
const problemCopy: Record<string, string> = {
  AUTH_REQUIRED: '当前 Web 会话已失效，请重新使用 QQ 登录', ORIGIN_REJECTED: '当前页面来源未被允许，请从正式 Web 地址打开',
  QQ_NOT_CONFIGURED: 'QQ 登录服务尚未配置完成，请联系管理员', QQ_PROVIDER_UNAVAILABLE: 'QQ 登录服务暂不可用，请稍后重试',
  QQ_LOGIN_INVALID: 'QQ 登录请求已失效，请重新登录', WEB_CSRF_COOKIE_MISSING: 'Web 安全会话不完整，请重新使用 QQ 登录',
  WEB_CSRF_COOKIE_INVALID: 'Web 安全会话无效，请重新使用 QQ 登录', AUTH_REQUEST_FAILED: '登录服务暂不可用，请稍后重试',
}
function publicProblem(result: ApiResult<unknown>, fallback: string): string {
  const code = result.problemCode ?? ''
  return Object.hasOwn(problemCopy, code) ? problemCopy[code]! : fallback
}

export interface WebAppProps { authClient?: WebAuthClient; navigateToProvider?: (url: string) => void }

export default function WebApp({ authClient = wowApi.webAuth, navigateToProvider = url => window.location.assign(url) }: WebAppProps) {
  const [phase, setPhase] = useState<AuthPhase>('checking')
  const [account, setAccount] = useState<MeResponse | null>(null)
  const [authContext, setAuthContext] = useState<WebClientAuth | null>(null)
  const [errorMessage, setErrorMessage] = useState(readAndClearLoginError)
  const authIntent = useRef(0)
  useEffect(() => { normalizeWebUrl(); window.addEventListener('hashchange', normalizeWebUrl); return () => window.removeEventListener('hashchange', normalizeWebUrl) }, [])

  const loadAccount = useCallback(async (intent = ++authIntent.current): Promise<boolean> => {
    const result = await authClient.me()
    if (intent !== authIntent.current) return false
    if (!result.fromFallback && isMeResponse(result.payload)) {
      try {
        const csrfToken = readWebCsrfCookie()
        setAccount(result.payload); setAuthContext({ kind: 'web', csrfToken }); setErrorMessage(''); setPhase('authenticated'); return true
      } catch (error) {
        const code = error instanceof Error ? error.message : 'WEB_CSRF_COOKIE_INVALID'
        setErrorMessage(problemCopy[code] ?? 'Web 安全会话无效，请重新使用 QQ 登录'); setPhase('blocked'); return false
      }
    }
    setAccount(null); setAuthContext(null)
    if (result.httpStatus === 401 || result.problemCode === 'AUTH_REQUIRED') { setPhase('signed_out'); return false }
    setErrorMessage(publicProblem(result, '账户状态暂不可用，请稍后重试')); setPhase('blocked'); return false
  }, [authClient])
  useEffect(() => { void loadAccount() }, [loadAccount])
  useEffect(() => {
    const restore = (event: PageTransitionEvent) => {
      if (!event.persisted) return
      setPhase('checking')
      void loadAccount()
    }
    window.addEventListener('pageshow', restore)
    return () => window.removeEventListener('pageshow', restore)
  }, [loadAccount])

  const login = async () => {
    if (phase === 'redirecting') return
    const intent = ++authIntent.current
    setErrorMessage(''); setPhase('redirecting')
    const result = await authClient.createQqLogin()
    if (intent !== authIntent.current) return
    if (result.fromFallback || !isQqLoginCreated(result.payload)) {
      setErrorMessage(publicProblem(result, 'QQ 登录入口暂不可用，请稍后重试')); setPhase('blocked'); return
    }
    navigateToProvider(result.payload.authorizationUrl)
  }
  const logout = async () => {
    const intent = ++authIntent.current
    if (!authContext) { setPhase('signed_out'); return }
    const result = await authClient.logout(authContext)
    if (intent !== authIntent.current) return
    if (result.fromFallback) { setErrorMessage(publicProblem(result, '退出登录失败，请稍后重试')); setPhase('blocked'); return }
    setAccount(null); setAuthContext(null); setPhase('signed_out')
  }
  if (phase === 'authenticated' && account && authContext) return <WebShell accountLabel={account.displayName || 'QQ 账号'} {...(account.avatarUrl ? { avatarUrl: account.avatarUrl } : {})} auth={authContext} onLogout={() => void logout()} />
  if (isTestLoginEnabled() && phase !== 'checking') return <TestLoginForm onLogin={async (testAccount, credential) => {
    const result = await authClient.loginTestWeb(testAccount, credential)
    if (result.fromFallback) throw new Error(result.problemCode || 'TEST_LOGIN_FAILED')
    if (!await loadAccount()) throw new Error('TEST_LOGIN_FAILED')
  }} />
  const waiting = phase === 'checking' || phase === 'redirecting'
  return <WebLoginHome><div className={styles['card']} data-auth-phase={phase} data-auth-transport="credentials-include">
    <div className={styles['status']} role="status" aria-live="polite">{waiting ? (phase === 'checking' ? '正在检查登录状态…' : '正在前往 QQ 授权…') : errorMessage || '使用 QQ 授权登录，继续查看你的对话与模拟记录。'}</div>
    <div className={styles['actions']}>{phase !== 'checking' ? <button type="button" className={styles['primaryButton']} disabled={phase === 'redirecting'} onClick={() => void login()}>
      <img className={styles['qqLogo']} src="https://wiki.connect.qq.com/wp-content/uploads/2016/12/Connect_logo_1.png" width="16" height="16" alt="" referrerPolicy="no-referrer" />
      {phase === 'redirecting' ? '正在跳转…' : 'QQ登录'}
    </button> : null}</div>
  </div></WebLoginHome>
}
