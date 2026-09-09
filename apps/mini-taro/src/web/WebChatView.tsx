import { ChatImages, ChatImageDrafts } from '../components/ChatImages'
import { readChatImageFiles } from '../features/chat/image-picker'
import { useChatImages } from '../features/chat/use-chat-images'
import ChatReplyDetails from '../components/ChatReplyDetails'
import ChatFeedback from '../components/ChatFeedback'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useRef, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'

import { ChatModel, type ChatModelState } from '../features/chat/chat-model'
import styles from './WebApp.module.scss'
import WebMessage from './WebMessage'
import WebThemeArt from './WebThemeArt'
import type { WebThemeId } from './web-themes'
import WebReplyStatus from './WebReplyStatus'
import WebConversationHistory from './WebConversationHistory'
import { useChatAutoScroll } from './use-chat-auto-scroll'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>

const quickPrompts = [
  '帮我看看元素萨的手法',
  '帮我分析WCL的数据',
  '帮我看看这场战斗如何提升',
]

export interface WebChatViewProps {
  auth: WebClientAuth
  themeId?: WebThemeId
}

export default function WebChatView({ auth, themeId = 'horde' }: WebChatViewProps) {
  const model = useMemo(() => new ChatModel(wowApi.chat, () => auth), [auth])
  const [state, setState] = useState<ChatModelState>(() => model.get())
  const [draft, setDraft] = useState('')
  const imageDraft = useChatImages(() => auth, state.phase !== 'signed_out')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const composing = useRef(false)
  const [dragging, setDragging] = useState(false)
  const dragDepth = useRef(0)
  const sending = state.phase === 'sending'
  const showWelcome = state.phase === 'ready' && !state.activeConversation?.messages.length
    && !state.pendingUserContent && !state.streamText && !state.streamProgress && !state.streamCompletedAt
  const messageList = useRef<HTMLDivElement>(null)
  const messageContent = useRef<HTMLDivElement>(null)
  const scrollRevision = useMemo(() => ({ text: state.streamText, progress: state.streamProgress, messages: state.activeConversation?.messages }),
    [state.streamText, state.streamProgress, state.activeConversation?.messages])
  const { paused, jumpToLatest } = useChatAutoScroll(messageList, messageContent,
    state.activeConversation?.id ?? '', sending, scrollRevision)
  const canSend = Boolean((draft.trim() || imageDraft.items.length) && state.activeConversation)
    && !imageDraft.pending
    && !sending && state.phase !== 'loading' && state.phase !== 'signed_out'

  useEffect(() => {
    const unsubscribe = model.subscribe(setState)
    void model.load()
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model])

  useEffect(() => {
    const resize = () => {
      const input = textarea.current
      if (!input) return
      input.style.height = '0px'
      input.style.height = `${Math.min(132, Math.max(42, input.scrollHeight))}px`
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [draft])

  const send = () => {
    if (!canSend || model.get().phase === 'sending') return
    model.send(draft, imageDraft.images, () => { setDraft(current => current === draft ? '' : current); imageDraft.clear() })
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
                disabled={state.phase === 'loading'}
                onClick={() => void model.create()}
              >
                + 新对话
              </button>
            </View>
            <WebConversationHistory conversations={state.conversations}
              activeId={state.activeConversation?.id ?? ''} hasMore={Boolean(state.nextCursor)}
              onOpen={(id) => void model.open(id)} onDelete={id => model.remove(id)} />
            {state.nextCursor ? (
              <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.loadMore()}>
                加载更多
              </Button>
            ) : null}
            {!state.conversations.length && state.phase === 'ready' ? (
              <Text className={styles['emptyCopy'] ?? ''}>还没有服务端会话。</Text>
            ) : null}
          </ScrollView>
        </View>

        <View className={styles['chatPane'] ?? ''}>
          <div className={styles['chatCanvas']} data-empty={showWelcome}>
            <div className={styles['workspaceArt']} aria-hidden="true" data-decorative="true">
              <div className={styles['chatScene']}><WebThemeArt themeId={themeId} /></div>
            </div>
          <div ref={messageList} className={styles['messageList'] ?? ''} tabIndex={0} aria-label="聊天消息">
            <div ref={messageContent} className={styles['messageContent']}>
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
                <ChatImages images={message.images} auth={auth} />
                <WebMessage content={message.content} markdown={message.role !== 'user'} />
                {message.role === 'assistant' && message.resolved !== undefined ? <ChatFeedback
                  resolved={message.resolved} onSubmit={choice => model.setFeedback(message.id, choice)} /> : null}
              </View>
            ))}
            {state.pendingUserContent || state.pendingUserImages.length ? (
              <View className={styles['webUserMessage'] ?? ''} data-persisted="false">
                <Text className={styles['messageRole'] ?? ''}>发送中</Text>
                <ChatImages images={state.pendingUserImages} auth={auth} />
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
            {showWelcome ? (
              <View className={styles['emptyState'] ?? ''}>
                <Text className={styles['emptyTitle'] ?? ''}>准备好了，随时开始</Text>
                <Text className={styles['emptyDescription'] ?? ''}>
                  把你的手法、装备、输出疑惑交给鸡哥
                </Text>
                <View className={styles['emptyHint'] ?? ''}>
                  <View className={styles['emptyHintDot'] ?? ''} />
                  <Text>创建一个新对话，就从这里开始</Text>
                </View>
              </View>
            ) : null}
            </div>
          </div>

          </div>

          {state.phase === 'blocked' || state.phase === 'signed_out' ? (
            <View className={styles['inlineError'] ?? ''} data-error-code={state.errorCode}>
              <Text>{state.phase === 'signed_out' ? 'Web 登录已失效，请重新使用 QQ 登录' : state.errorMessage}</Text>
              <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.recover()}>
                重新读取历史
              </Button>
            </View>
          ) : null}

          <View className={styles['webComposer'] ?? ''}>
            {paused && !showWelcome ? <button type="button" className={styles['jumpToLatest'] ?? ''} onClick={jumpToLatest}>
              ↓ 回到最新
            </button> : null}
            <div className={styles['composerRow']} aria-label="消息输入区" data-dragging={dragging}
              onDragEnter={event => {
                if (!event.dataTransfer.types.includes('Files')) return
                event.preventDefault()
                dragDepth.current += 1
                if (imageDraft.enabled && !sending) setDragging(true)
              }}
              onDragOver={event => {
                if (!event.dataTransfer.types.includes('Files')) return
                event.preventDefault()
                event.dataTransfer.dropEffect = imageDraft.enabled && !sending ? 'copy' : 'none'
              }}
              onDragLeave={event => {
                if (!event.dataTransfer.types.includes('Files')) return
                dragDepth.current = Math.max(0, dragDepth.current - 1)
                if (!dragDepth.current) setDragging(false)
              }}
              onDrop={event => {
                dragDepth.current = 0
                setDragging(false)
                const files = Array.from(event.dataTransfer.files)
                if (!files.length) return
                event.preventDefault()
                if (imageDraft.enabled && !sending) void imageDraft.add(count => readChatImageFiles(files, count))
              }}>
              <ChatImageDrafts compact items={imageDraft.items} disabled={sending} remove={imageDraft.remove} retry={imageDraft.retry} />
              {imageDraft.error ? <div role="alert" className={styles['composerError']}>{imageDraft.error}</div> : null}
              {dragging ? <span className={styles['dropHint']} aria-hidden="true">松开即可添加图片</span> : null}
              <div className={styles['composerControls']} style={{gridTemplateColumns: imageDraft.enabled ? '34px minmax(0, 1fr) 42px' : 'minmax(0, 1fr) 42px'}}>
              {imageDraft.enabled ? <button className={styles['composerImageButton']} type="button" aria-label="添加图片" title="选择图片，也可粘贴或拖入" disabled={sending || imageDraft.items.length >= 3} onClick={() => void imageDraft.choose()}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r="1.5"/><path d="m4 17 5-5 4 4 3-3 5 5"/></svg>
              </button> : null}
              <textarea
                ref={textarea}
                className={styles['webTextarea'] ?? ''}
                maxLength={4000}
                rows={1}
                aria-label="消息内容"
                title="Enter 发送，Shift+Enter 换行"
                placeholder={imageDraft.enabled ? "问问鸡哥，也可粘贴或拖入图片" : "问问鸡哥"}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onPaste={event => {
                  const files = Array.from(event.clipboardData.files)
                  if (!files.length) return
                  event.preventDefault()
                  if (!imageDraft.enabled || sending) return
                  const text = event.clipboardData.getData('text/plain')
                  if (text) {
                    const {selectionStart, selectionEnd} = event.currentTarget
                    setDraft(current => (current.slice(0, selectionStart) + text + current.slice(selectionEnd)).slice(0, 4000))
                  }
                  void imageDraft.add(count => readChatImageFiles(files, count))
                }}
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
              </div>
            </div>
            {showWelcome ? (
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
