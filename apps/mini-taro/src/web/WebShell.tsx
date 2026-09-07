import { Button, Text, View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'

import WebChatView from './WebChatView'
import WebSimcView from './WebSimcView'
import WebServiceHealth from './WebServiceHealth'
import WebHeaderActions from './WebHeaderActions'
import WebFaqPage from './WebFaqPage'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>
type BusinessView = 'chat' | 'simc'
type WebView = BusinessView | 'faq'

function readView(): WebView {
  const view = new URLSearchParams(window.location.search).get('view')
  return view === 'faq' || view === 'simc' ? view : 'chat'
}

function viewHref(view: WebView): string {
  const url = new URL(window.location.href)
  if (view === 'chat') url.searchParams.delete('view')
  else url.searchParams.set('view', view)
  return url.pathname + url.search + url.hash
}

const modes: Array<{ id: BusinessView; number: string; label: string }> = [
  { id: 'chat', number: '01', label: '对话' },
  { id: 'simc', number: '02', label: '模拟' },
]

export interface WebShellProps {
  accountLabel: string
  auth: WebClientAuth
  onLogout: () => void
}

export default function WebShell({ accountLabel, auth, onLogout }: WebShellProps) {
  const [avatar, setAvatar] = useState<string | null>(null)
  const refreshAvatar = useRef<() => void>(() => undefined)
  useEffect(() => {
    let alive = true
    let generation = 0
    const refresh = async () => {
      const current = ++generation
      try {
        const result = await wowApi.avatar.get(auth)
        if (alive && current === generation && !result.fromFallback) setAvatar(result.payload.avatarDataUrl)
      } catch { /* Avatar availability does not affect the authenticated workspace. */ }
    }
    const visible = () => { if (document.visibilityState === 'visible') void refresh() }
    refreshAvatar.current = () => { void refresh() }
    void refresh()
    window.addEventListener('focus', visible)
    document.addEventListener('visibilitychange', visible)
    return () => {
      alive = false
      refreshAvatar.current = () => undefined
      window.removeEventListener('focus', visible)
      document.removeEventListener('visibilitychange', visible)
    }
  }, [auth])
  const [activeView, setActiveView] = useState<WebView>(readView)
  const [simcVisited, setSimcVisited] = useState(() => readView() === 'simc')
  const lastBusinessView = useRef<BusinessView>(activeView === 'simc' ? 'simc' : 'chat')

  const showView = (view: WebView) => {
    if (view === 'simc') setSimcVisited(true)
    if (view !== 'faq') lastBusinessView.current = view
    setActiveView(view)
  }
  const navigate = (view: WebView) => {
    if (view !== activeView) window.history.pushState(window.history.state, '', viewHref(view))
    showView(view)
  }
  useEffect(() => {
    const restore = () => {
      const view = readView()
      if (view === 'simc') setSimcVisited(true)
      if (view !== 'faq') lastBusinessView.current = view
      setActiveView(view)
    }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [])

  return (
    <View
      className={styles['workspace'] ?? ''}
      data-business-view={activeView}
      data-skin="horde"
    >
      <View className={styles['workspaceTopbar'] ?? ''}>
        <View className={styles['brand'] ?? ''}>
          <View className={styles['brandMascotFrame'] ?? ''}>
            <View className={styles['brandMascot'] ?? ''} />
          </View>
          <View className={styles['brandCopy'] ?? ''}>
            <Text className={styles['brandName'] ?? ''}>炸鸡队长来啦</Text>
          </View>
          <WebServiceHealth />
        </View>

        <View className={styles['modeSwitch'] ?? ''}>
          {modes.map((mode) => (
            <Button
              key={mode.id}
              className={styles['navButton'] ?? ''}
              data-active={activeView === mode.id ? 'true' : 'false'}
              aria-label={mode.id === 'simc' ? 'SimC 模拟' : '队长对话'}
              onClick={() => navigate(mode.id)}
            >
              <Text className={styles['modeSwitchNumber'] ?? ''}>{mode.number}</Text>
              <Text>{mode.label}</Text>
            </Button>
          ))}
        </View>

        <WebHeaderActions avatarDataUrl={avatar} onRefreshAvatar={() => refreshAvatar.current()} accountLabel={accountLabel} onLogout={onLogout}
          faqActive={activeView === 'faq'} faqHref={viewHref('faq')} onFaq={() => navigate('faq')} />
      </View>

      <View className={styles['workspaceBody'] ?? ''}>
        <View className={styles['workspaceMain'] ?? ''}>
          {activeView === 'chat' ? (
            <View className={styles['workspaceArt'] ?? ''} data-decorative="true">
              <View className={styles['chatArtCrop'] ?? ''}>
                <View className={styles['chatScene'] ?? ''} />
                <View className={styles['chatArtWash'] ?? ''} />
                <View className={`${styles['chatCloud'] ?? ''} ${styles['chatCloudBack'] ?? ''}`} />
                <View className={`${styles['chatCloud'] ?? ''} ${styles['chatCloudFront'] ?? ''}`} />
              </View>
            </View>
          ) : null}

          {activeView === 'faq' ? <WebFaqPage
            returnLabel={lastBusinessView.current === 'simc' ? '返回模拟' : '返回对话'}
            onReturn={() => navigate(lastBusinessView.current)} /> : null}

          {/* A tab change must not dispose the chat model and abort its active stream. */}
          <div className={styles['businessPane']} hidden={activeView !== 'chat'}>
            <WebChatView auth={auth} />
          </div>
          {simcVisited ? (
            <div className={styles['businessPane']} hidden={activeView !== 'simc'}>
              <WebSimcView auth={auth} />
            </div>
          ) : null}
        </View>
      </View>
    </View>
  )
}
