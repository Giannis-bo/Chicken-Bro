import { ScrollView, Text, Textarea, View } from '@tarojs/components'
import type { ReactNode } from 'react'

import type { LegacyChatMessage as ChatMessage, ReadinessState } from '@wow-mini/domain'

import { ActionButton } from './ActionButton'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { ownerClass, ownerStyle } from './style'

export interface ChatShellProps {
  messages: readonly ChatMessage[]
  draft: string
  inputState: Extract<ReadinessState, 'ready' | 'loading' | 'blocked' | 'error' | 'unknown'>
  placeholder?: string
  tabRoot?: boolean
  context?: ReactNode
  showTopicDrawerGlyph?: boolean | undefined
  onDraftChange: (value: string) => void
  onSend: () => void
  onRetry?: () => void
}

export function ChatShell({
  messages,
  draft,
  inputState,
  tabRoot = false,
  placeholder = '描述职业、专精、场景和问题',
  context,
  showTopicDrawerGlyph = false,
  onDraftChange,
  onSend,
  onRetry,
}: ChatShellProps) {
  const blocked = inputState === 'blocked' || inputState === 'loading'
  return (
    <View className={ownerClass(ownerStyle('chat'), tabRoot && ownerStyle('chatTabRoot'))}>
      {context ? (
        <View
          className={ownerStyle('chatContext')}
          data-slot-id="slot-chat-context-frame"
        >
          {showTopicDrawerGlyph ? (
            <SystemGlyph
              assetId="utility-glyph-family.topic"
              className={ownerStyle('chatContextGlyph')}
              slotId="slot-topic-drawer-glyph"
            />
          ) : null}
          {context}
        </View>
      ) : null}
      <ScrollView className={ownerStyle('chatStream')} scrollY scrollWithAnimation>
        <View className={ownerStyle('chatMessages')}>
          {messages.map((message, index) => (
            <View
              key={message.messageId ?? `${message.role}-${index}`}
              className={ownerClass(
                ownerStyle('chatBubble'),
                message.role === 'user' ? ownerStyle('chatUser') : ownerStyle('chatAssistant'),
              )}
            >
              <Text>{message.content}</Text>
              {message.status ? <Text className={ownerStyle('chatMeta')}>{message.status}</Text> : null}
            </View>
          ))}
          {inputState === 'error' ? (
            <View>
              <StatusVisual detail="消息未发送，不会生成本地假回答。" state="error" />
              {onRetry ? <ActionButton variant="danger" onClick={onRetry}>重试</ActionButton> : null}
            </View>
          ) : null}
        </View>
      </ScrollView>
      <View
        className={ownerClass(ownerStyle('inputDock'), tabRoot && ownerStyle('inputDockTabRoot'))}
        data-slot-id="slot-input-dock-frame"
      >
        <Textarea
          autoHeight
          className={ownerStyle('input')}
          disabled={blocked}
          maxlength={2000}
          placeholder={placeholder}
          value={draft}
          onInput={(event) => onDraftChange(event.detail.value)}
        />
        <ActionButton
          disabled={blocked || !draft.trim()}
          loading={inputState === 'loading'}
          variant="primaryGold"
          onClick={onSend}
        >
          发送
        </ActionButton>
      </View>
    </View>
  )
}
