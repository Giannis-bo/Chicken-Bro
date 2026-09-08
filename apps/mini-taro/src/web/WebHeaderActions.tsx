import { useEffect, useId, useRef, useState } from 'react'

import WebHelpDialog from './WebHelpDialog'
import WebThemeDialog from './WebThemeDialog'
import type { WebThemeId } from './web-themes'
import styles from './WebHeaderActions.module.scss'

export default function WebHeaderActions({ accountLabel, onLogout, faqActive, faqHref, onFaq, avatarDataUrl, onRefreshAvatar, themeId = 'horde', onSelectTheme, themeSaveFailed = false }: {
  themeId?: WebThemeId
  onSelectTheme?: (id: WebThemeId) => void
  themeSaveFailed?: boolean
  avatarDataUrl?: string | null
  onRefreshAvatar?: () => void
  accountLabel: string
  onLogout: () => void
  faqActive: boolean
  faqHref: string
  onFaq: () => void
}) {
  const [failedAvatar, setFailedAvatar] = useState<string | null>(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [changelogOpen, setChangelogOpen] = useState(false)
  const [themeOpen, setThemeOpen] = useState(false)
  const accountRef = useRef<HTMLDivElement>(null)
  const avatarRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!accountOpen) return
    const dismissOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !accountRef.current?.contains(event.target)) setAccountOpen(false)
    }
    const dismissEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setAccountOpen(false)
      avatarRef.current?.focus()
    }
    document.addEventListener('pointerdown', dismissOutside)
    document.addEventListener('keydown', dismissEscape)
    return () => {
      document.removeEventListener('pointerdown', dismissOutside)
      document.removeEventListener('keydown', dismissEscape)
    }
  }, [accountOpen])

  return (
    <div className={styles['actions']}>
      <a className={styles['helpLink']} href={faqHref} aria-current={faqActive ? 'page' : undefined}
        onClick={event => {
          if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
          event.preventDefault()
          setAccountOpen(false)
          onFaq()
        }}>FAQ</a>
      <button type="button" className={styles['helpLink']} aria-haspopup="dialog"
        onClick={() => { setAccountOpen(false); setChangelogOpen(true) }}>更新日志</button>
      <div ref={accountRef} className={styles['account']}
        onBlur={event => {
          if (!event.currentTarget.contains(event.relatedTarget)) setAccountOpen(false)
        }}>
        <button ref={avatarRef} type="button" className={styles['avatar']} aria-label="账户菜单"
          title={accountLabel} aria-expanded={accountOpen} aria-controls={accountOpen ? panelId : undefined}
          onClick={() => { if (!accountOpen) onRefreshAvatar?.(); setAccountOpen(value => !value) }}>
          {avatarDataUrl && avatarDataUrl !== failedAvatar ? <img className={styles['avatarImage']} src={avatarDataUrl} alt="" onError={() => setFailedAvatar(avatarDataUrl)} /> : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="8" r="3.5" />
            <path d="M5 21v-2a7 7 0 0 1 14 0v2" />
          </svg>)}
          <span className={styles['onlineDot']} />
        </button>
        {accountOpen ? (
          <div id={panelId} className={styles['accountPanel']}>
            <span className={styles['accountCaption']}>当前账号</span>
            <span className={styles['accountName']}>{accountLabel}</span>
            {onSelectTheme ? <button type="button" aria-label="修改主题" aria-haspopup="dialog" className={styles['themeAction']}
              onClick={() => { setAccountOpen(false); setThemeOpen(true) }}>修改主题 <span aria-hidden="true">◈</span></button> : null}
            <button type="button" aria-label="退出登录" className={styles['logout']}
              onClick={() => { setAccountOpen(false); onLogout() }}>
              退出登录 <span aria-hidden="true">↗</span>
            </button>
          </div>
        ) : null}
      </div>
      {changelogOpen ? <WebHelpDialog onClose={() => setChangelogOpen(false)} /> : null}
      {themeOpen && onSelectTheme ? <WebThemeDialog selected={themeId} onSelect={onSelectTheme} saveFailed={themeSaveFailed}
        returnFocus={avatarRef} onClose={() => setThemeOpen(false)} /> : null}
    </div>
  )
}
