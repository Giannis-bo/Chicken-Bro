export const loginErrorCopy = {
  QQ_LOGIN_CANCELLED: '你已取消 QQ 授权，可以重新登录。',
  QQ_LOGIN_INVALID: 'QQ 登录请求已失效，请重新登录。',
  QQ_PROVIDER_UNAVAILABLE: 'QQ 登录服务暂不可用，请稍后重试。',
  QQ_LOGIN_FAILED: 'QQ 登录未完成，请重试。',
} as const

export function readAndClearLoginError(): string {
  if (typeof window === 'undefined') return ''
  const url = new URL(window.location.href)
  const raw = url.searchParams.get('loginError')
  if (raw === null) return ''
  url.searchParams.delete('loginError')
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
  return loginErrorCopy[raw as keyof typeof loginErrorCopy] ?? loginErrorCopy.QQ_LOGIN_FAILED
}
