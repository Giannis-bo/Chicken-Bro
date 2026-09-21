import { Button, Text, View } from '@tarojs/components'
import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties } from 'react'
import type { GameId } from '@wow-mini/domain'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'

import { readWebView as readView, webViewHref as viewHref, type WebView } from './web-routing'
import PoweredBy from '../components/PoweredBy'
import WebChatView from './WebChatView'
import WebSimcView from './WebSimcView'
import WebServiceHealth from './WebServiceHealth'
import WebHeaderActions from './WebHeaderActions'
import WebFaqPage from './WebFaqPage'
import { readWebTheme, resolveWebTheme, saveWebTheme, themeStorageKey, type WebThemeId } from './web-themes'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>
type BusinessView = 'chat' | 'simc' | 'poe2'
const WebPoe2 = lazy(() => import('./WebPoe2'))
const readGame = (): GameId => new URL(window.location.href).searchParams.get('game') === 'poe2' || readView() === 'poe2' ? 'poe2' : 'wow'

export interface WebShellProps {
  accountLabel: string
  avatarUrl?: string
  auth: WebClientAuth
  onLogout: () => void
}

export default function WebShell({ accountLabel, avatarUrl, auth, onLogout }: WebShellProps) {
  const [isAdmin, setIsAdmin] = useState(false)
  useEffect(() => {
    let alive = true
    void wowApi.admin?.access(auth).then(result => { if (alive) setIsAdmin(!result.fromFallback && result.payload?.isAdmin === true) }).catch(() => { if (alive) setIsAdmin(false) })
    return () => { alive = false }
  }, [auth])
  const [themeId, setThemeId] = useState(readWebTheme)
  const [themeSaveFailed, setThemeSaveFailed] = useState(false)
  const theme = resolveWebTheme(themeId)
  const selectTheme = (id: WebThemeId) => {
    setThemeId(id)
    setThemeSaveFailed(!saveWebTheme(id))
  }
  useEffect(() => {
    const restore = (event: StorageEvent) => {
      if (event.key === themeStorageKey || event.key === null) {
        setThemeId(readWebTheme())
        setThemeSaveFailed(false)
      }
    }
    window.addEventListener('storage', restore)
    return () => window.removeEventListener('storage', restore)
  }, [])
  const [avatar, setAvatar] = useState<string | null>(avatarUrl ?? null)
  const refreshAvatar = useRef<() => void>(() => undefined)
  useEffect(() => {
    let alive = true
    let generation = 0
    const refresh = async () => {
      const current = ++generation
      try {
        const result = await wowApi.avatar.get(auth)
        if (alive && current === generation && !result.fromFallback && result.payload.avatarDataUrl) setAvatar(result.payload.avatarDataUrl)
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
  const [activeView, setActiveView] = useState<WebView>(() => readView())
  const [game, setGame] = useState<GameId>(readGame)
  const [poe2Visited, setPoe2Visited] = useState(() => readView() === 'poe2')
  const [poe2ChatVisited, setPoe2ChatVisited] = useState(() => readGame() === 'poe2')
  const modes: Array<{ id: BusinessView; number: string; label: string }> = [
    { id: 'chat', number: '01', label: '对话' },
    game === 'poe2' ? { id: 'poe2', number: '02', label: '构筑' } : { id: 'simc', number: '02', label: '模拟' },
  ]
  const [simcVisited, setSimcVisited] = useState(() => readView() === 'simc')
  const lastBusinessView = useRef<BusinessView>(activeView === 'simc' ? 'simc' : 'chat')

  const showView = (view: WebView) => {
    if (view === 'simc') setSimcVisited(true)
    if (view === 'poe2') setPoe2Visited(true)
    if (view === 'chat' || view === 'simc' || view === 'poe2') lastBusinessView.current = view
    setActiveView(view)
  }
  const navigate = (view: WebView) => {
    if (view !== activeView) window.history.pushState(window.history.state, '', viewHref(view))
    showView(view)
  }
  const selectGame = (nextGame: GameId) => {
    if (nextGame === game) return
    setGame(nextGame)
    if (nextGame === 'poe2') setPoe2ChatVisited(true)
    const url = new URL(window.location.href)
    url.searchParams.set('game', nextGame)
    window.history.pushState(window.history.state, '', viewHref('chat', url))
    showView('chat')
  }
  useEffect(() => {
    const restore = () => {
      const view = readView()
      const nextGame = readGame()
      setGame(nextGame)
      if (nextGame === 'poe2') setPoe2ChatVisited(true)
      if (view === 'simc') setSimcVisited(true)
      if (view === 'poe2') setPoe2Visited(true)
      if (view === 'chat' || view === 'simc' || view === 'poe2') lastBusinessView.current = view
      setActiveView(view)
    }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [])

  return (
    <View
      className={styles['workspace'] ?? ''}
      data-business-view={activeView}
      data-skin={theme.id}
      style={{ '--accent': theme.accent, '--accent-soft': theme.soft, '--sidebar-bg': theme.sidebar } as CSSProperties}
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

        <div className={styles['workspaceNavigation']}>
          <div className={styles['gameSwitch']} role="group" aria-label="选择游戏">
            {([{ id: 'wow', label: '魔兽世界' }, { id: 'poe2', label: '流放之路 2' }] as const).map(option => (
              <button key={option.id} type="button" className={styles['gameButton']} aria-pressed={game === option.id} onClick={() => selectGame(option.id)}>
                {option.label}
              </button>
            ))}
          </div>
          <View className={styles['modeSwitch'] ?? ''}>
          {modes.map((mode) => (
            <Button
              key={mode.id}
              className={styles['navButton'] ?? ''}
              data-active={activeView === mode.id ? 'true' : 'false'}
              aria-label={mode.id === 'simc' ? 'SimC 模拟' : mode.id === 'poe2' ? 'POE2 构筑' : '队长对话'}
              onClick={() => navigate(mode.id)}
            >
              <Text className={styles['modeSwitchNumber'] ?? ''}>{mode.number}</Text>
              <Text>{mode.label}</Text>
            </Button>
          ))}
          </View>
        </div>

        <WebHeaderActions {...(isAdmin ? { adminHref: viewHref('admin') } : {})} avatarDataUrl={avatar} onRefreshAvatar={() => refreshAvatar.current()} accountLabel={accountLabel} onLogout={onLogout}
          themeId={themeId} onSelectTheme={selectTheme} themeSaveFailed={themeSaveFailed}
          faqActive={activeView === 'faq'} faqHref={viewHref('faq')} onFaq={() => navigate('faq')} />
      </View>

      <View className={styles['workspaceBody'] ?? ''}>
        <View className={styles['workspaceMain'] ?? ''}>
          {activeView === 'faq' ? <WebFaqPage
            returnLabel={lastBusinessView.current === 'simc' ? '返回模拟' : '返回对话'}
            onReturn={() => navigate(lastBusinessView.current)} /> : null}

          {/* A tab change must not dispose the chat model and abort its active stream. */}
          <div className={styles['businessPane']} hidden={activeView !== 'chat' || game !== 'wow'}>
            <WebChatView auth={auth} themeId={themeId} game="wow" />
          </div>
          {poe2ChatVisited ? <div className={styles['businessPane']} hidden={activeView !== 'chat' || game !== 'poe2'}>
            <WebChatView auth={auth} themeId={themeId} game="poe2" />
          </div> : null}
          {poe2Visited ? <div className={styles['businessPane']} hidden={activeView !== 'poe2'}>
            <Suspense fallback={<p>正在加载构筑工作台…</p>}><WebPoe2 auth={auth} /></Suspense>
          </div> : null}
          {simcVisited ? (
            <div className={styles['businessPane']} hidden={activeView !== 'simc'}>
              <WebSimcView auth={auth} themeId={themeId} />
            </div>
          ) : null}
          <PoweredBy />
        </View>
      </View>
    </View>
  )
}
