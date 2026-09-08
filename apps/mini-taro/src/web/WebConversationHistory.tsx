import { useEffect, useId, useMemo, useState, useRef } from 'react'
import type { ConversationSummary } from '@wow-mini/domain'
import styles from './WebApp.module.scss'
import deleteStyles from './WebConversationHistory.module.scss'

const calendar = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

function displayDate(value: string) {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return { day: '日期未知', time: '--:--', timestamp: 0 }
  const parts = new Map(calendar.formatToParts(timestamp).map(part => [part.type, part.value]))
  return {
    day: `${parts.get('year')}-${parts.get('month')}-${parts.get('day')}`,
    time: `${parts.get('hour')}:${parts.get('minute')}`, timestamp,
  }
}

export interface WebConversationHistoryProps {
  conversations: readonly ConversationSummary[]
  activeId: string
  hasMore: boolean
  onOpen: (id: string) => void
  onDelete?: (id: string) => Promise<string | null>
}

export default function WebConversationHistory({ conversations, activeId, hasMore, onOpen, onDelete }: WebConversationHistoryProps) {
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null)
  const prefix = useId().replace(/:/g, '')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const groups = useMemo(() => {
    const items = conversations.map(conversation => ({ conversation, ...displayDate(conversation.updatedAt) }))
      .sort((a, b) => b.timestamp - a.timestamp)
    const days = new Map<string, typeof items>()
    items.forEach(item => {
      const day = days.get(item.day) ?? []
      day.push(item)
      days.set(item.day, day)
    })
    return [...days].map(([day, entries]) => ({ day, entries }))
  }, [conversations])
  const activeDay = groups.find(group => group.entries.some(item => item.conversation.id === activeId))?.day
  useEffect(() => {
    if (activeDay) setExpanded(previous => ({ ...previous, [activeDay]: true }))
  }, [activeId, activeDay])

  return <div className={styles['historyGroups']}>
    {groups.map((group, index) => {
      const open = expanded[group.day] ?? index === 0
      const id = `history-${prefix}-${group.day}`
      const partial = hasMore && index === groups.length - 1
      return <section key={group.day} className={styles['historyDay']}>
        <button type="button" className={styles['historyDayToggle']} aria-expanded={open} aria-controls={id}
          onClick={() => setExpanded(previous => ({ ...previous, [group.day]: !open }))}>
          <span className={styles['historyDayChevron']} aria-hidden="true" />
          <span>{group.day}</span>
          <span className={styles['historyDayCount']}> · {partial ? `已加载 ${group.entries.length} 个` : `${group.entries.length} 个会话`}</span>
        </button>
        {open ? <div id={id} className={styles['historyDayItems']}>
          {group.entries.map(({ conversation, time }) => <div key={conversation.id} className={deleteStyles['row']}><button type="button"
            className={`${styles['sideListButton']} ${deleteStyles['conversationButton']}`} data-conversation-id={conversation.id}
            data-active={activeId === conversation.id ? 'true' : 'false'}
            aria-current={activeId === conversation.id ? 'true' : undefined}
            onClick={() => onOpen(conversation.id)}>
            <span className={styles['conversationTitle']} title={conversation.title || '炸鸡队长对话'}>
              {conversation.title || '炸鸡队长对话'}
            </span>
            <time className={styles['listMeta']} dateTime={conversation.updatedAt}>{time}</time>
          </button>
          {onDelete ? <button type="button" className={deleteStyles['trash']} title="删除会话" aria-label={`删除会话：${conversation.title || '炸鸡队长对话'}`}
            onClick={() => setDeleting(conversation)}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" />
            </svg>
          </button> : null}</div>)}
        </div> : null}
      </section>
    })}
    {deleting && onDelete ? <DeleteDialog conversation={deleting} onDelete={onDelete} onClose={() => setDeleting(null)} /> : null}
  </div>
}


function DeleteDialog({ conversation, onDelete, onClose }: {
  conversation: ConversationSummary; onDelete: (id: string) => Promise<string | null>; onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  const inFlight = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const titleId = useId()
  useEffect(() => {
    const focus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = ref.current!
    dialog.showModal()
    cancel.current?.focus()
    return () => { dialog.close(); if (focus?.isConnected) focus.focus() }
  }, [])
  const submit = async () => {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    try {
      const failure = await onDelete(conversation.id)
      if (failure) setError(failure)
      else onClose()
    } catch { setError('删除失败，请稍后重试。') }
    finally { inFlight.current = false; setBusy(false) }
  }
  return <dialog ref={ref} className={deleteStyles['dialog']} aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); if (!inFlight.current) onClose() }}>
    <h2 id={titleId}>删除会话？</h2>
    <p>“{conversation.title || '炸鸡队长对话'}”及其消息将从网页和小程序历史中移除。</p>
    {error ? <p role="alert" className={deleteStyles['error']}>{error}</p> : null}
    <div className={deleteStyles['actions']}>
      <button ref={cancel} className={deleteStyles['actionButton']} type="button" disabled={busy} onClick={onClose}>取消</button>
      <button type="button" className={`${deleteStyles['actionButton']} ${deleteStyles['confirm']}`} disabled={busy} onClick={() => void submit()}>{busy ? '删除中…' : '删除'}</button>
    </div>
  </dialog>
}
