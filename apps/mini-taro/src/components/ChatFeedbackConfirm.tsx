import { useEffect, useId, useRef } from 'react'
import styles from './ChatFeedbackConfirm.module.scss'

interface Props {
  resolved: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ChatFeedbackConfirm({ resolved, onConfirm, onCancel }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  const titleId = useId()
  const descriptionId = useId()
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const element = dialog.current!
    element.showModal()
    cancel.current?.focus()
    return () => { element.close(); if (previous?.isConnected) previous.focus() }
  }, [])
  return <dialog ref={dialog} className={styles['dialog']} aria-labelledby={titleId} aria-describedby={descriptionId}
    onCancel={event => { event.preventDefault(); onCancel() }}>
    <h2 id={titleId}>确认「{resolved ? '已解决' : '未解决'}」反馈？</h2>
    <p id={descriptionId}>您的反馈会让鸡哥变得更好。</p>
    <div className={styles['actions']}>
      <button ref={cancel} type="button" onClick={onCancel}>取消</button>
      <button type="button" className={styles['confirm']} onClick={onConfirm}>确认</button>
    </div>
  </dialog>
}
