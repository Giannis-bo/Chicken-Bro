import { useEffect, useId, useRef, useState } from 'react'

import WebHelpDialog from './WebHelpDialog'
import WebThemeDialog from './WebThemeDialog'
import type { WebThemeId } from './web-themes'
import { faqGroups } from '../features/help/faq-content'
import { releases } from '../features/help/release-content'
import { useHelpReadStatus } from './use-help-read-status'
import styles from './WebHeaderActions.module.scss'

// Compare the exact public content so same-day edits count, unrelated builds do not.
const helpRevisions = { faq: JSON.stringify(faqGroups), changelog: JSON.stringify(releases) }

export default function WebHeaderActions({ adminHref, accountLabel, onLogout, faqActive, faqHref, onFaq, avatarDataUrl, onRefreshAvatar, themeId = 'horde', onSelectTheme, themeSaveFailed = false }: {
  adminHref?: string
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
  const { unread, markRead } = useHelpReadStatus(helpRevisions)
  useEffect(() => { if (faqActive) markRead('faq') }, [faqActive, markRead])
  useEffect(() => { if (changelogOpen) markRead('changelog') }, [changelogOpen, markRead])
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
      <a className={styles['helpLink']} href="https://github.com/boyuan19910222-ui/Chicken-Bro"
        target="_blank" rel="noopener noreferrer" aria-label="GitHub 仓库（在新标签页打开）">GitHub</a>
      <a className={styles['helpLink']} href={faqHref} aria-current={faqActive ? 'page' : undefined}
        aria-label={unread.faq ? 'FAQ（有更新）' : 'FAQ'}
        onClick={event => {
          if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
          event.preventDefault()
          setAccountOpen(false)
          onFaq()
        }}>FAQ{unread.faq ? <span className={styles['unreadDot']} aria-hidden="true" /> : null}</a>
      <button type="button" className={styles['helpLink']} aria-haspopup="dialog"
        aria-label={unread.changelog ? '更新日志（有更新）' : '更新日志'}
        onClick={() => { setAccountOpen(false); setChangelogOpen(true) }}>更新日志{unread.changelog ? <span className={styles['unreadDot']} aria-hidden="true" /> : null}</button>
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
            {adminHref ? <a className={styles['themeAction']} href={adminHref}>运营后台 <span aria-hidden="true">↗</span></a> : null}
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
