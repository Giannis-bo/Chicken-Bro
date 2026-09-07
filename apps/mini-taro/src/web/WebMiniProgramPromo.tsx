import { useEffect, useId, useRef, useState } from 'react'

import artwork from './assets/mini-program-promo.png'
import styles from './WebMiniProgramPromo.module.scss'

function PromoDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current!
    dialog.showModal()
    return () => {
      dialog.close()
      previousFocus?.focus()
    }
  }, [])

  return <dialog ref={dialogRef} className={styles['dialog']} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose() }}
    onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <div className={styles['dialogInner']}>
      <header className={styles['dialogHeader']}>
        <h2 id={titleId}>手机上，继续和鸡哥聊</h2>
        <button type="button" className={styles['close']} aria-label="关闭小程序码" onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="m6 6 12 12M18 6 6 18" />
          </svg>
        </button>
      </header>
      <img className={styles['artwork']} src={artwork} width="2172" height="800"
        alt="微信扫一扫，或搜一搜「炸鸡队长来啦」小程序" />
      <p className={styles['hint']}>打开微信扫一扫，随时聊魔兽、看模拟。</p>
    </div>
  </dialog>
}

export default function WebMiniProgramPromo() {
  const [open, setOpen] = useState(false)
  return <aside className={styles['promo']} aria-label="炸鸡队长小程序">
    <button type="button" className={styles['trigger']} aria-label="放大小程序码"
      aria-haspopup="dialog" title="点击放大，用微信扫码打开小程序" onClick={() => setOpen(true)}>
      <img className={styles['artwork']} src={artwork} width="2172" height="800"
        alt="微信搜一搜：炸鸡队长来啦" />
    </button>
    {open ? <PromoDialog onClose={() => setOpen(false)} /> : null}
  </aside>
}
