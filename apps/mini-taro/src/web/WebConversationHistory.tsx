import { useEffect, useId, useMemo, useState } from 'react'
import type { ConversationSummary } from '@wow-mini/domain'
import styles from './WebApp.module.scss'

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
}

export default function WebConversationHistory({ conversations, activeId, hasMore, onOpen }: WebConversationHistoryProps) {
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
          {group.entries.map(({ conversation, time }) => <button key={conversation.id} type="button"
            className={styles['sideListButton']} data-conversation-id={conversation.id}
            data-active={activeId === conversation.id ? 'true' : 'false'}
            aria-current={activeId === conversation.id ? 'true' : undefined}
            onClick={() => onOpen(conversation.id)}>
            <span className={styles['conversationTitle']} title={conversation.title || '炸鸡队长对话'}>
              {conversation.title || '炸鸡队长对话'}
            </span>
            <time className={styles['listMeta']} dateTime={conversation.updatedAt}>{time}</time>
          </button>)}
        </div> : null}
      </section>
    })}
  </div>
}
