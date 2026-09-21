export type WebView = 'chat' | 'simc' | 'poe2' | 'faq' | 'admin'

const publicPath = typeof __WOW_H5_PUBLIC_PATH__ === 'string' ? __WOW_H5_PUBLIC_PATH__ : '/'
const webBase = publicPath.replace(/\/+$/u, '')

export function readWebView(url = new URL(window.location.href), base = webBase): WebView {
  const view = url.searchParams.get('view')
  if (url.pathname.replace(/\/+$/u, '') === `${base}/admin` || view === 'admin') return 'admin'
  if (view === 'faq') return 'faq'
  if (url.pathname.replace(/\/+$/u, '') === `${base}/poe2` || view === 'builds') return 'poe2'
  if (url.pathname.replace(/\/+$/u, '') === `${base}/simc` || view === 'simc') return 'simc'
  return 'chat'
}

export function webViewHref(view: WebView, url = new URL(window.location.href), base = webBase): string {
  const next = new URL(url.href)
  next.pathname = view === 'admin' ? `${base}/admin` : view === 'simc' ? `${base}/simc` : view === 'poe2' ? `${base}/poe2` : `${base}/`
  next.searchParams.delete('view')
  if (view === 'faq') next.searchParams.set('view', 'faq')
  if (view === 'poe2') next.searchParams.set('game', 'poe2')
  if (view === 'simc') next.searchParams.delete('game')
  // Only remove the legacy Web host page fragment; preserve unrelated anchors.
  if (/^#\/pages\/chickenbro\/index\/?$/u.test(next.hash)) next.hash = ''
  return next.pathname + next.search + next.hash
}

export function normalizeWebUrl(): void {
  const url = new URL(window.location.href)
  const next = webViewHref(readWebView(url), url)
  if (next !== url.pathname + url.search + url.hash) {
    window.history.replaceState(window.history.state, '', next)
  }
}
