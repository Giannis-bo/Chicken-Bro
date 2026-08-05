import Taro from '@tarojs/taro'
import { ScrollView, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useState } from 'react'

import type { ChatMessage, ChickenbroSessionSummary } from '@wow-mini/domain'

import { ControlButton } from './ControlButton'
import { SystemGlyph } from './SystemGlyph'

import styles from './ChickenbroChatComponents.module.scss'

export interface ChickenbroTranscriptProps {
  messages: readonly ChatMessage[]
  state: 'idle' | 'loading' | 'ready' | 'error'
  onRetry: () => void
  temporaryAssistantText?: string
  scrollTop?: number
  hasUnseen?: boolean
  onScroll?: (detail: { scrollTop: number; scrollHeight: number; clientHeight: number }) => void
  onReturnToLatest?: () => void
}

function messageKey(message: ChatMessage, index: number): string {
  return message.messageId || `${message.role}-${index}-${message.content.slice(0, 16)}`
}

function attachmentRefs(message: ChatMessage): readonly string[] {
  return message.role === 'assistant' ? message.payload?.evidenceRefs ?? [] : []
}

function evidenceOutcomeLabel(message: ChatMessage): string {
  if (message.role !== 'assistant') return ''
  const labels = {
    answered: '已完成证据判断',
    partial: '部分证据',
    researching: '受控检索中',
    blocked: '当前不可执行',
  } as const
  const outcome = message.payload?.evidenceOutcome
  return outcome && outcome in labels ? labels[outcome] : ''
}

export function ChickenbroTranscript({
  messages,
  state,
  onRetry,
  temporaryAssistantText = '',
  scrollTop = 0,
  hasUnseen = false,
  onScroll,
  onReturnToLatest,
}: ChickenbroTranscriptProps) {
  const [clientHeight, setClientHeight] = useState(0)
  useEffect(() => {
    try {
      Taro.createSelectorQuery()
        .select('#chickenbro-transcript-scroll')
        .boundingClientRect((rect) => {
          const value = Array.isArray(rect) ? rect[0] : rect
          setClientHeight(Math.max(0, Number(value?.height) || 0))
        })
        .exec()
    } catch {
      // Scroll auto-follow remains disabled until the native view reports its height.
    }
  }, [messages.length, temporaryAssistantText])

  if (messages.length === 0) {
    return (
      <View className={styles['emptyConversation'] ?? ''} data-owner="chickenbro-transcript" data-region="captain_greeting">
        <SystemGlyph assetId="utility-glyph-family.assistant" slotId="asset_slot.captain-assistant-identity" />
        <View>
          <Text>我是炸鸡队长。</Text>
          <Text>直接说说你想了解的正式服或测试服问题。</Text>
        </View>
      </View>
    )
  }

  return (
    <View className={styles['transcriptShell'] ?? ''} data-owner="chickenbro-transcript" data-region="captain_transcript" data-state={state}>
      <ScrollView
        className={styles['transcriptScroll'] ?? ''}
        data-role="chickenbro-transcript-scroll"
        id="chickenbro-transcript-scroll"
        scrollY
        scrollTop={scrollTop}
        onScroll={(event) => onScroll?.({
          scrollTop: Number(event.detail.scrollTop) || 0,
          scrollHeight: Number(event.detail.scrollHeight) || 0,
          clientHeight,
        })}
      >
        <View className={styles['transcript'] ?? ''}>
          {messages.map((message, index) => {
            const refs = attachmentRefs(message)
            const outcomeLabel = evidenceOutcomeLabel(message)
            return (
              <View key={messageKey(message, index)} className={styles[message.role === 'user' ? 'userMessage' : 'assistantMessage'] ?? ''} data-role={`chickenbro-message-${message.role}`}>
                <View className={styles['messageBubble'] ?? ''}>
                  {outcomeLabel ? <View className={styles['evidenceOutcome'] ?? ''} data-role="chickenbro-evidence-outcome"><Text>{outcomeLabel}</Text></View> : null}
                  <Text>{message.content}</Text>
                  {refs.length > 0 ? (
                    <View className={styles['attachmentList'] ?? ''} data-region="captain_attachment">
                      {refs.map((reference) => (
                        <View key={reference} className={styles['attachment'] ?? ''} data-role="chickenbro-answer-attachment">
                          <SystemGlyph assetId="utility-glyph-family.document" slotId="asset_slot.captain-attachment" />
                          <Text>{reference}</Text>
                        </View>
                      ))}
                    </View>
                  ) : null}
                </View>
              </View>
            )
          })}
          {temporaryAssistantText ? (
            <View className={styles['assistantMessage'] ?? ''} data-role="chickenbro-message-assistant-temporary">
              <View className={styles['messageBubble'] ?? ''}><Text>{temporaryAssistantText}</Text></View>
            </View>
          ) : null}
          {state === 'loading' && !temporaryAssistantText ? <Text className={styles['pending'] ?? ''}>炸鸡队长正在回复…</Text> : null}
          {state === 'error' ? (
            <ControlButton className={styles['retryAction'] ?? ''} data-role="chickenbro-retry" onClick={onRetry}>重试发送</ControlButton>
          ) : null}
        </View>
      </ScrollView>
      {hasUnseen && onReturnToLatest ? (
        <ControlButton className={styles['returnLatest'] ?? ''} data-role="chickenbro-return-latest" onClick={onReturnToLatest}>回到最新</ControlButton>
      ) : null}
    </View>
  )
}

export interface ChickenbroComposerProps {
  draft: string
  state: 'idle' | 'loading' | 'ready' | 'error'
  onDraftChange: (value: string) => void
  onSend: () => void
}

export function ChickenbroComposer({ draft, state, onDraftChange, onSend }: ChickenbroComposerProps) {
  const loading = state === 'loading'
  const sendDisabled = loading || !draft.trim()
  return (
    <View className={styles['composer'] ?? ''} data-owner="chickenbro-composer" data-region="composer_dock" data-state={state}>
      <Textarea
        className={styles['composerInput'] ?? ''}
        data-role="chickenbro-composer"
        disabled={loading}
        maxlength={2000}
        placeholder="问问版本、职业或副本…"
        value={draft}
        onInput={(event) => onDraftChange(event.detail.value)}
      />
      <ControlButton
        className={styles['sendAction'] ?? ''}
        data-role="chickenbro-dock-send"
        data-disabled={sendDisabled ? 'true' : 'false'}
        disabled={sendDisabled}
        onClick={onSend}
      >
        <SystemGlyph assetId="utility-glyph-family.send" slotId="asset_slot.captain-composer" />
        <Text>{loading ? '回复中' : '发送'}</Text>
      </ControlButton>
    </View>
  )
}

export interface ChickenbroArchiveListProps {
  sessions: readonly ChickenbroSessionSummary[]
  state: 'loading' | 'ready' | 'empty' | 'error'
  hasMore: boolean
  onSelect: (session: ChickenbroSessionSummary) => void
  onLoadMore: () => void
  onRetry: () => void
}

function archiveTime(value: string): string {
  return value.replace('T', ' ').replace(/:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/u, '').slice(0, 16)
}

export function ChickenbroArchiveList({ sessions, state, hasMore, onSelect, onLoadMore, onRetry }: ChickenbroArchiveListProps) {
  if (state === 'loading' && sessions.length === 0) {
    return <View className={styles['archiveState'] ?? ''} data-region="archive_terminal"><Text>正在读取对话存档…</Text></View>
  }
  if (state === 'error') {
    return (
      <View className={styles['archiveState'] ?? ''} data-region="archive_terminal">
        <Text>存档暂时无法读取。</Text>
        <ControlButton data-role="chickenbro-archive-retry" onClick={onRetry}>重试</ControlButton>
      </View>
    )
  }
  if (state === 'empty') {
    return <View className={styles['archiveState'] ?? ''} data-region="archive_terminal"><Text>还没有对话</Text></View>
  }
  return (
    <View className={styles['archiveList'] ?? ''} data-owner="chickenbro-archive-list" data-region="archive_list">
      {sessions.map((session) => (
        <ControlButton
          key={session.sessionId}
          className={styles['archiveRow'] ?? ''}
          data-role="chickenbro-archive-session"
          data-session-id={session.sessionId}
          onClick={() => onSelect(session)}
        >
          <View>
            <Text>{session.title}</Text>
            <Text>{session.productPhase === 'ptr' ? '测试服对话' : '正式服对话'}</Text>
          </View>
          <View>
            <Text>{archiveTime(session.updatedAt)}</Text>
            <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.archive-row-disclosure" />
          </View>
        </ControlButton>
      ))}
      {hasMore ? <ControlButton className={styles['loadMore'] ?? ''} data-role="chickenbro-archive-load-more" onClick={onLoadMore}>继续加载</ControlButton> : null}
    </View>
  )
}
