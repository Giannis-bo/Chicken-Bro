export type WebView = 'chat' | 'simc' | 'faq'

const publicPath = typeof __WOW_H5_PUBLIC_PATH__ === 'string' ? __WOW_H5_PUBLIC_PATH__ : '/'
const webBase = publicPath.replace(/\/+$/u, '')

export function readWebView(url = new URL(window.location.href), base = webBase): WebView {
  const view = url.searchParams.get('view')
  if (view === 'faq') return 'faq'
  if (url.pathname.replace(/\/+$/u, '') === `${base}/simc` || view === 'simc') return 'simc'
  return 'chat'
}

export function webViewHref(view: WebView, url = new URL(window.location.href), base = webBase): string {
  const next = new URL(url.href)
  next.pathname = view === 'simc' ? `${base}/simc` : `${base}/`
  next.searchParams.delete('view')
  if (view === 'faq') next.searchParams.set('view', 'faq')
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
