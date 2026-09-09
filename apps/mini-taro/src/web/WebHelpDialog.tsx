import { useEffect, useId, useRef } from 'react'
import { isTestLoginEnabled } from '../features/auth/test-login-mode'

import styles from './WebHeaderActions.module.scss'


const releases = [
  { date: '2026-09-08', title: '炸鸡队长来啦 1.0 正式上线', items: [
    '与鸡哥聊魔兽、运行云端模拟，并在当前 QQ 账号中继续对话。',
  ] },
  { date: '2026-09-07', title: '更清爽的导航与账号入口', items: [
    '点击右上角头像查看当前账号并退出登录。',
    'FAQ 改为独立页面，支持直接链接与浏览器返回；更新日志可随时查看。',
    '移除主题口号、历史对话旁头像及侧栏底部装饰。',
  ] },
  { date: '2026-09-06', title: '模拟工作台与报告升级', items: [
    '新增模拟参数、任务列表与结构化结果展示。',
    '改进国服角色和战斗日志导入，补充链接格式提示。',
    '逐步补齐技能、召唤物及增益的中文名称，部分名称仍待完善。',
    '鸡哥可按需发起云端模拟；切换对话和模拟时，回答可以继续生成。',
  ] },
  { date: '2026-09-05', title: '聊天阅读和历史记录优化', items: [
    '历史对话按日期分组，支持展开和收起。',
    '优化回复排版、文字选择、输入区与等待提示。',
    '长回复自动跟随，上翻或选择文字时暂停跟随。',
  ] },
]

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
