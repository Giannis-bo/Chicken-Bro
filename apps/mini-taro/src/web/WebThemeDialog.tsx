import { useEffect, useId, useRef, type RefObject } from 'react'
import { webThemes, type WebThemeId } from './web-themes'
import styles from './WebThemeDialog.module.scss'

export default function WebThemeDialog({ selected, onSelect, onClose, saveFailed, returnFocus }: {
  returnFocus: RefObject<HTMLButtonElement>
  selected: WebThemeId
  onSelect: (id: WebThemeId) => void
  onClose: () => void
  saveFailed: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const title = useId()
  useEffect(() => {
    const dialog = ref.current!
    dialog.showModal()
    dialog.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus()
    return () => { dialog.close(); returnFocus.current?.focus() }
  }, [returnFocus])
  return <dialog ref={ref} className={styles['dialog']} aria-labelledby={title}
    onCancel={event => { event.preventDefault(); onClose() }}
    onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <header className={styles['header']}>
      <div><h2 id={title}>修改主题</h2><p>选择喜欢的艾泽拉斯风景</p></div>
      <button type="button" onClick={onClose} aria-label="关闭修改主题" className={styles['close']}>×</button>
    </header>
    <div className={styles['body']}>
      <div className={styles['grid']} aria-label="主题列表">
        {webThemes.map(theme => <button type="button" key={theme.id} data-theme-choice={theme.id}
          className={styles['card']} aria-label={theme.name} aria-pressed={selected === theme.id}
          onClick={() => onSelect(theme.id)}>
          <img src={theme.image} alt="" loading="lazy" width="300" height="200" />
          <span className={styles['name']}>{theme.name}</span>
          <span className={styles['meta']}><i style={{ background: theme.accent }} />{theme.color}
            {selected === theme.id ? <span className={styles['selected']}>✓ 使用中</span> : null}</span>
        </button>)}
      </div>
    </div>
    <footer className={styles['footer']}>{saveFailed ? <span role="status">主题已切换，但浏览器无法保存，刷新后可能恢复默认。</span> : null}
      <button type="button" onClick={onClose}>完成</button></footer>
  </dialog>
}
