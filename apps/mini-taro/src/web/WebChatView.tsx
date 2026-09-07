import ChatReplyDetails from '../components/ChatReplyDetails'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useRef, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'

import { ChatModel, type ChatModelState } from '../features/chat/chat-model'
import styles from './WebApp.module.scss'
import WebMessage from './WebMessage'
import WebReplyStatus from './WebReplyStatus'
import WebConversationHistory from './WebConversationHistory'
import WebMiniProgramPromo from './WebMiniProgramPromo'
import { useChatAutoScroll } from './use-chat-auto-scroll'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>

const quickPrompts = [
  '帮我看看元素萨满的装备',
  '从一个模拟开始',
  '聊聊鸡哥的新皮肤',
]

export interface WebChatViewProps {
  auth: WebClientAuth
}

export default function WebChatView({ auth }: WebChatViewProps) {
  const model = useMemo(() => new ChatModel(wowApi.chat, () => auth), [auth])
  const [state, setState] = useState<ChatModelState>(() => model.get())
  const [draft, setDraft] = useState('')
  const composing = useRef(false)
  const sending = state.phase === 'sending'
  const messageList = useRef<HTMLDivElement>(null)
  const messageContent = useRef<HTMLDivElement>(null)
  const scrollRevision = useMemo(() => ({ text: state.streamText, progress: state.streamProgress, messages: state.activeConversation?.messages }),
    [state.streamText, state.streamProgress, state.activeConversation?.messages])
  const { paused, jumpToLatest } = useChatAutoScroll(messageList, messageContent,
    state.activeConversation?.id ?? '', sending, scrollRevision)
  const canSend = Boolean(draft.trim() && state.activeConversation)
    && !sending && state.phase !== 'loading' && state.phase !== 'signed_out'

  useEffect(() => {
    const unsubscribe = model.subscribe(setState)
    void model.load()
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model])

  const send = () => {
    if (!canSend || model.get().phase === 'sending') return
    const task = model.send(draft)
    if (task) setDraft('')
  }

  return (
    <View className={styles['businessView'] ?? ''} data-chat-phase={state.phase}>
      <View className={styles['splitView'] ?? ''}>
        <View className={styles['historyColumn'] ?? ''}>
          <ScrollView className={styles['sideList'] ?? ''} scrollY>
            <View className={styles['sideListIntro'] ?? ''}>
              <View>
                <Text className={styles['sideListIntroTitle'] ?? ''}>历史对话</Text>
              </View>
              <button
                type="button"
                className={styles['newConversationButton'] ?? ''}
                disabled={state.phase === 'loading' || state.phase === 'sending'}
                onClick={() => void model.create()}
              >
                + 新对话
              </button>
            </View>
            <WebConversationHistory conversations={state.conversations}
              activeId={state.activeConversation?.id ?? ''} hasMore={Boolean(state.nextCursor)}
              onOpen={(id) => void model.open(id)} />
            {state.nextCursor ? (
              <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.loadMore()}>
                加载更多
              </Button>
            ) : null}
            {!state.conversations.length && state.phase === 'ready' ? (
              <Text className={styles['emptyCopy'] ?? ''}>还没有服务端会话。</Text>
            ) : null}
          </ScrollView>
          <WebMiniProgramPromo />
        </View>

        <View className={styles['chatPane'] ?? ''}>
          <div ref={messageList} className={styles['messageList'] ?? ''} tabIndex={0} aria-label="聊天消息">
            <div ref={messageContent}>
            {state.activeConversation?.messages.map((message) => (
              <View
                key={message.id}
                className={styles[message.role === 'user' ? 'webUserMessage' : 'webAssistantMessage'] ?? ''}
                data-message-id={message.id}
                data-persisted="true"
              >
                <Text className={styles['messageRole'] ?? ''}>{message.role === 'user' ? '你' : '鸡哥'}</Text>
                {message.role === 'assistant' ? <ChatReplyDetails text={message.progress?.text ?? ''}
                  status={message.progress?.status ?? 'completed'} completedAt={message.progress?.completedAt ?? message.createdAt}
                  durationMs={message.progress?.durationMs ?? null} /> : null}
                <WebMessage content={message.content} markdown={message.role !== 'user'} />
              </View>
            ))}
            {state.pendingUserContent ? (
              <View className={styles['webUserMessage'] ?? ''} data-persisted="false">
                <Text className={styles['messageRole'] ?? ''}>发送中</Text>
                <WebMessage content={state.pendingUserContent} />
              </View>
            ) : null}
            {sending && !state.streamText && !state.streamProgress ? <WebReplyStatus /> : null}
            {state.streamText || state.streamProgress || state.streamCompletedAt ? (
              <View className={styles['webAssistantMessage'] ?? ''} data-persisted="false">
                <Text className={styles['messageRole'] ?? ''}>鸡哥</Text>
                <ChatReplyDetails text={state.streamProgress} status={state.streamProgressStatus}
                  completedAt={state.streamCompletedAt} durationMs={state.streamDurationMs} />
                <WebMessage content={state.streamText} markdown />
              </View>
            ) : null}
            {!state.activeConversation && state.phase === 'ready' ? (
              <View className={styles['emptyState'] ?? ''}>
                <Text className={styles['emptyEyebrow'] ?? ''}>WOW COMPANION / 对话</Text>
                <Text className={styles['emptyTitle'] ?? ''}>准备好了，随时开始</Text>
                <Text className={styles['emptyDescription'] ?? ''}>
                  把你的副本目标、装备疑问或输出困惑交给鸡哥，先聊清楚再行动。
                </Text>
                <View className={styles['emptyHint'] ?? ''}>
                  <View className={styles['emptyHintDot'] ?? ''} />
                  <Text>创建一个新对话，就从这里开始</Text>
                </View>
              </View>
            ) : null}
            </div>
          </div>

          {state.phase === 'blocked' || state.phase === 'signed_out' ? (
            <View className={styles['inlineError'] ?? ''} data-error-code={state.errorCode}>
              <Text>{state.phase === 'signed_out' ? 'Web 登录已失效，请重新扫码登录' : state.errorMessage}</Text>
              <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.recover()}>
                重新读取历史
              </Button>
            </View>
          ) : null}

          <View className={styles['webComposer'] ?? ''}>
            {paused ? <button type="button" className={styles['jumpToLatest'] ?? ''} onClick={jumpToLatest}>
              ↓ 回到最新
            </button> : null}
            <View className={styles['composerRow'] ?? ''}>
              <Text className={styles['composerAdd'] ?? ''}>＋</Text>
              <textarea
                className={styles['webTextarea'] ?? ''}
                maxLength={4000}
                rows={1}
                aria-label="消息内容"
                title="Enter 发送，Shift+Enter 换行"
                placeholder="问问鸡哥"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onCompositionStart={() => { composing.current = true }}
                onCompositionEnd={() => { composing.current = false }}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter' || event.shiftKey || composing.current
                    || event.nativeEvent.isComposing || event.keyCode === 229) return
                  event.preventDefault()
                  if (!event.repeat) send()
                }}
              />
              <button
                type="button"
                className={styles['primaryButton'] ?? ''}
                disabled={!canSend}
                aria-label={sending ? '正在回复' : '发送消息'}
                aria-busy={sending}
                onClick={send}
              >
                {sending ? <span className={styles['composerSpinner'] ?? ''} role="status" aria-label="正在回复" />
                  : <span aria-hidden="true">↑</span>}
              </button>
            </View>
            {!state.activeConversation && state.phase === 'ready' ? (
              <View className={styles['quickPrompts'] ?? ''}>
                {quickPrompts.map((prompt) => (
                  <Button
                    key={prompt}
                    className={styles['quickPrompt'] ?? ''}
                    size="mini"
                    onClick={() => setDraft(prompt)}
                  >
                    {prompt}
                  </Button>
                ))}
              </View>
            ) : null}
            <Text className={styles['composerFootnote'] ?? ''}>鸡哥可能会犯错，请核对重要信息。</Text>
          </View>
        </View>
      </View>
    </View>
  )
}
