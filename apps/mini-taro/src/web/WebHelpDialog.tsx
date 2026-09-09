import { useEffect, useId, useRef } from 'react'
import { isTestLoginEnabled } from '../features/auth/test-login-mode'

import { releases } from '../features/help/release-content'
import styles from './WebHeaderActions.module.scss'

export default function WebHelpDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const headingId = useId()

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current!
    dialog.showModal()
    return () => {
      dialog.close()
      previousFocus?.focus()
    }
  }, [])

  return (
    <dialog ref={dialogRef} className={styles['dialog']} aria-labelledby={headingId}
      onCancel={event => { event.preventDefault(); onClose() }}
      onClick={event => { if (event.target === event.currentTarget) onClose() }}>
      <div className={styles['dialogInner']}>
        <header className={styles['dialogHeader']}>
          <span className={styles['eyebrow']}>产品动态</span>
          <h2 id={headingId}>更新日志</h2>
          <button type="button" className={styles['closeButton']} aria-label="关闭更新日志" onClick={onClose}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <path d="m6 6 12 12M18 6 6 18" />
            </svg>
          </button>
        </header>
        <div className={styles['dialogBody']}>
              {releases.map(release => (
                <article key={release.date} className={styles['release']}>
                  <div className={styles['releaseMeta']}><time dateTime={release.date}>{release.date}</time><span>{isTestLoginEnabled() ? '测试版' : '功能更新'}</span></div>
                  <h3>{release.title}</h3>
                  <ul>{release.items.map(item => <li key={item}>{item}</li>)}</ul>
                </article>
              ))}
        </div>
      </div>
    </dialog>
  )
}
