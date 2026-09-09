import { ChatImages, ChatImageDrafts } from '../../components/ChatImages'
import { useChatImages } from '../../features/chat/use-chat-images'
import ChatReplyDetails from '../../components/ChatReplyDetails'
import ChatFeedback from '../../components/ChatFeedback'
import { MiniHelpActions } from '../../components/MiniHelp'
import { useTabRootIdentity } from '../../use-tab-root-identity'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import { Button, Image, ScrollView, Text, Textarea, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ConversationSummary } from '@wow-mini/domain'
import { wowApi } from '@wow-mini/api-client'
import { MiniSessionStore } from '../../features/auth/mini-session'
import { ChatModel, type ChatModelState } from '../../features/chat/chat-model'
import MiniMessage from '../../components/MiniMessage'
import mascot from '../../web/assets/gu-gu-mascot.png'
import styles from './index.module.scss'

function ChickenbroPage() {
  useTabRootIdentity('pages/chickenbro/index')
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(() => new ChatModel(wowApi.chat, () => sessions.createAuthContext()), [sessions])
  const [state, setState] = useState<ChatModelState>(() => model.get())
  const [draft, setDraft] = useState('')
  const imageAuth = useMemo(() => { try { return sessions.createAuthContext() } catch { return null } }, [sessions, state.phase])
  const imageDraft = useChatImages(() => sessions.createAuthContext(), Boolean(imageAuth))
  const inputSession = useRef(0)
  const renderedInputSession = inputSession.current
  const [historyOpen, setHistoryOpen] = useState(false)
  useEffect(() => {
    if (!historyOpen) return
    void Taro.hideTabBar?.({ animation: false }).catch(() => undefined)
    return () => { void Taro.showTabBar?.({ animation: false }).catch(() => undefined) }
  }, [historyOpen])
  const [deletingId, setDeletingId] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const deleteInFlight = useRef(false)
  const [following, setFollowing] = useState(true)
  const [endAnchor, setEndAnchor] = useState('chat-end-0')
  const [elapsed, setElapsed] = useState(0)
  const [preparing, setPreparing] = useState(false)
  const sending = useRef(false)
  const mounted = useRef(true)
  const lastScroll = useRef(0)
  const touching = useRef(false)
  const scrollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const busy = preparing || state.phase === 'sending' || state.phase === 'loading'

  useEffect(() => {
    mounted.current = true
    const unsubscribe = model.subscribe((next) => {
      setState(next)
      if (isTestLoginEnabled() && next.phase === 'signed_out') sessions.invalidate()
    })
    return () => { mounted.current = false; unsubscribe(); model.dispose() }
  }, [model, sessions])

  const loginAndLoad = async () => {
    try {
      if (!sessions.getValid()) await sessions.login()
      if (model.get().phase === 'sending') return
      if (model.get().activeConversation) await model.recover()
      else await model.load()
    } catch { await model.recover() }
  }
  useEffect(() => { if (isTestLoginEnabled() || sessions.getValid()) void loginAndLoad() }, [model, sessions])
  useDidShow(() => { void loginAndLoad() })

  useEffect(() => {
    if (!following) {
      if (scrollTimer.current) clearTimeout(scrollTimer.current)
      scrollTimer.current = null
      return
    }
    // Throttle rather than debounce: continuous deltas must not starve scrolling.
    if (scrollTimer.current) return
    scrollTimer.current = setTimeout(() => {
      scrollTimer.current = null
      setEndAnchor((value) => value === 'chat-end-0' ? 'chat-end-1' : 'chat-end-0')
    }, 100)
  }, [following, state.activeConversation, state.streamText, state.streamProgress, state.pendingUserContent])
  useEffect(() => () => { if (scrollTimer.current) clearTimeout(scrollTimer.current) }, [])
  useEffect(() => {
    setElapsed(0)
    if (state.phase !== 'sending') return
    const started = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [state.phase])

  const send = async () => {
    if (sending.current || busy || (!draft.trim() && !imageDraft.items.length) || imageDraft.pending || state.phase !== 'ready') return
    sending.current = true
    setPreparing(true)
    const content = draft.trim()
    try {
      if (!model.get().activeConversation) {
        const created = await model.create(content.slice(0, 32))
        if (!created || !mounted.current) return
      }
      model.send(content, imageDraft.images, () => {
        // Replace the native editor and reject late IME events from the sent draft.
        inputSession.current += 1
        setDraft(current => current.trim() === content ? '' : current)
        imageDraft.clear()
        setFollowing(true)
        void Taro.hideKeyboard?.().catch(() => undefined)
      })
    } finally { sending.current = false; if (mounted.current) setPreparing(false) }
  }
  const retry = () => {
    if (state.phase === 'signed_out') {
      void sessions.logout().catch(() => undefined).finally(() => loginAndLoad())
      return
    }
    void model.recover()
  }
  const startNew = async () => {
    if (preparing || state.phase === 'loading') return
    if (draft.trim() || imageDraft.items.length) {
      const answer = await Taro.showModal({ title: '新建对话', content: '当前还有未发送的内容。新建后将清空输入框。', confirmText: '新建' })
      if (!answer.confirm || !mounted.current) return
    }
    setPreparing(true)
    try {
      const created = await model.create()
      if (created && mounted.current) { setDraft(''); imageDraft.discard(); setHistoryOpen(false); setFollowing(true) }
    } finally { if (mounted.current) setPreparing(false) }
  }

  const removeConversation = async (conversation: ConversationSummary) => {
    if (deleteInFlight.current) return
    deleteInFlight.current = true
    setDeleteError('')
    setDeletingId(conversation.id)
    try {
      const answer = await Taro.showModal({
        title: '删除会话？',
        content: `“${conversation.title || '炸鸡队长对话'}”及其消息将从网页和小程序历史中移除。`,
        confirmText: '删除', cancelText: '取消', confirmColor: '#9e5145',
      })
      if (!answer.confirm || !mounted.current) return
      const failure = await model.remove(conversation.id)
      if (mounted.current && failure) setDeleteError(failure)
    } catch {
      if (mounted.current) setDeleteError('删除失败，请稍后重试。')
    } finally {
      deleteInFlight.current = false
      if (mounted.current) setDeletingId('')
    }
  }

  return <View className={styles['page'] ?? ''} data-chat-phase={state.phase}>
    <View className={styles['header'] ?? ''}>
      <Button className={styles['historyButton'] ?? ''} aria-expanded={historyOpen} onClick={() => { void Taro.hideKeyboard?.().catch(() => undefined); setHistoryOpen(true) }}>
        历史对话 ☰
      </Button>
      <Button className={styles['secondaryButton'] ?? ''} disabled={preparing || state.phase === 'loading'} onClick={() => void startNew()}>＋ 新对话</Button>
      <MiniHelpActions />
    </View>
    {historyOpen ? <View className={styles['drawerLayer'] ?? ''}>
      <Button className={styles['drawerMask'] ?? ''} aria-label="关闭历史抽屉遮罩" onClick={() => setHistoryOpen(false)} />
      <View className={styles['drawer'] ?? ''}>
        <View className={styles['drawerHeader'] ?? ''}><Text className={styles['drawerTitle'] ?? ''}>历史会话</Text><Button className={styles['drawerClose'] ?? ''} aria-label="关闭历史会话" onClick={() => setHistoryOpen(false)}>关闭</Button></View>
        <ScrollView className={styles['history'] ?? ''} scrollY>
      {deleteError ? <Text className={styles['deleteError'] ?? ''}>{deleteError}</Text> : null}
      {state.conversations.map((conversation, index) => <View key={conversation.id} className={styles['conversationRow'] ?? ''}><Button
        className={`${styles['conversationButton']} ${state.activeConversation?.id === conversation.id ? styles['activeConversation'] : ''}`}
        disabled={preparing} onClick={() => {
          setHistoryOpen(false); setFollowing(true); void model.open(conversation.id)
        }}>
        <Text className={styles['conversationTitle'] ?? ''}>{conversation.title || `对话 ${state.conversations.length - index}`}</Text>
        <Text className={styles['conversationTime'] ?? ''}>{new Date(conversation.updatedAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</Text>
      </Button>
        <Button className={styles['deleteButton'] ?? ''} aria-label={`删除会话：${conversation.title || '炸鸡队长对话'}`}
          disabled={Boolean(deletingId)} onClick={() => void removeConversation(conversation)}>
          {deletingId === conversation.id ? '处理中' : '删除'}
        </Button>
      </View>)}
      {state.nextCursor ? <Button className={styles['secondaryButton'] ?? ''} disabled={preparing || state.phase === 'loading'} onClick={() => void model.loadMore()}>加载更多对话</Button> : null}
      {!state.conversations.length ? <Text className={styles['hint'] ?? ''}>还没有历史对话</Text> : null}
        </ScrollView>
      </View>
    </View> : null}
    <ScrollView className={styles['messages'] ?? ''} scrollY scrollIntoView={endAnchor}
      onTouchStart={() => { touching.current = true }} onTouchEnd={() => { touching.current = false }}
      onScroll={(event) => {
        if (touching.current && event.detail.scrollTop < lastScroll.current - 3) setFollowing(false)
        lastScroll.current = event.detail.scrollTop
      }}>
      <View className={styles['messageList'] ?? ''}>
        {state.activeConversation?.messages.map((message) => <View key={message.id}
          className={styles[message.role === 'user' ? 'userMessage' : 'assistantMessage'] ?? ''} data-persisted="true">
          <View className={styles['messageRole'] ?? ''}>
            {message.role !== 'user' ? <Image className={styles['replyMascot'] ?? ''} src={mascot} mode="aspectFit" /> : null}
            <Text>{message.role === 'user' ? '我' : '鸡哥'}</Text>
          </View>
          {message.role === 'assistant' ? <ChatReplyDetails text={message.progress?.text ?? ''}
            status={message.progress?.status ?? 'completed'} completedAt={message.progress?.completedAt ?? message.createdAt}
            durationMs={message.progress?.durationMs ?? null} /> : null}
          {imageAuth ? <ChatImages images={message.images} auth={imageAuth} /> : null}
          <MiniMessage content={message.content} markdown={message.role !== 'user'} />
          {message.role === 'assistant' && message.resolved !== undefined ? <ChatFeedback
            resolved={message.resolved} onSubmit={choice => model.setFeedback(message.id, choice)} /> : null}
        </View>)}
        {state.pendingUserContent || state.pendingUserImages.length ? <View className={styles['userMessage'] ?? ''} data-persisted="false">
          {imageAuth ? <ChatImages images={state.pendingUserImages} auth={imageAuth} /> : null}
          <Text className={styles['messageRole'] ?? ''}>我</Text><MiniMessage content={state.pendingUserContent} />
        </View> : null}
        {state.phase === 'sending' || state.streamProgress || state.streamText || state.streamCompletedAt ? <View className={styles['assistantMessage'] ?? ''} data-persisted="false">
          <View className={styles['messageRole'] ?? ''}>
            <Image className={styles['replyMascot'] ?? ''} src={mascot} mode="aspectFit" />
            <Text>鸡哥 · {state.streamProgressStatus === 'failed' ? '未完成' : state.streamCompletedAt ? '已回复' : state.streamText ? '正在回复' : `正在思考${elapsed >= 10 ? ` · ${elapsed} 秒` : '…'}`}</Text>
          </View>
          <ChatReplyDetails text={state.streamProgress} status={state.streamProgressStatus}
            completedAt={state.streamCompletedAt} durationMs={state.streamDurationMs} />
          {state.streamText ? <MiniMessage content={state.streamText} markdown /> : !state.streamProgress ? <Text className={styles['hint'] ?? ''}>正在整理你的问题，查询日志或模拟可能需要一些时间。</Text> : null}
        </View> : null}
        {state.phase === 'loading' ? <Text className={styles['hint'] ?? ''}>正在读取对话…</Text> : null}
        {(!state.activeConversation || state.activeConversation.messages.length === 0) && state.phase === 'ready' ? <View className={styles['empty'] ?? ''}>
          <Image className={styles['emptyMascot'] ?? ''} src={mascot} mode="aspectFit" />
          <Text className={styles['emptyTitle'] ?? ''}>今天想和鸡哥聊什么？</Text>
          <Text className={styles['hint'] ?? ''}>贴一段战斗日志，或聊聊手法、配装和模拟。</Text>
          {['帮我分析这场战斗', '我想优化角色配装'].map((prompt) => <Button key={prompt} className={styles['suggestion'] ?? ''} onClick={() => setDraft(prompt)}>{prompt} ↗</Button>)}
        </View> : null}
        <View id="chat-end-0" className={styles['anchor'] ?? ''} /><View id="chat-end-1" className={styles['anchor'] ?? ''} />
      </View>
    </ScrollView>
    {!following ? <Button className={styles['backToLatest'] ?? ''} onClick={() => setFollowing(true)}>↓ 回到最新</Button> : null}
    {state.phase === 'blocked' || state.phase === 'signed_out' ? <View className={styles['errorCard'] ?? ''} data-error-code={state.errorCode}>
      <Text>{state.errorMessage || '会话暂不可用'}</Text>
      <Button className={styles['secondaryButton'] ?? ''} onClick={retry}>{state.phase === 'signed_out' ? '重新登录' : '重新读取历史'}</Button>
    </View> : null}
    <ChatImageDrafts items={imageDraft.items} disabled={busy} remove={imageDraft.remove} retry={imageDraft.retry} />
    {imageDraft.error ? <Text>{imageDraft.error}</Text> : null}
    {imageDraft.enabled ? <Button disabled={busy || imageDraft.items.length >= 3} onClick={() => void imageDraft.choose()}>＋ 图片</Button> : null}
    <View className={styles['composer'] ?? ''}>
      <Textarea key={renderedInputSession} className={styles['textarea'] ?? ''} maxlength={4000} placeholder="发消息给鸡哥…" value={draft}
        autoHeight adjustPosition cursorSpacing={24} holdKeyboard confirmType="send" showConfirmBar={false}
        disabled={preparing} onConfirm={() => void send()} onInput={(event) => {
          if (renderedInputSession === inputSession.current) setDraft(event.detail.value)
        }} />
      <Button className={styles['sendButton'] ?? ''} disabled={busy || (!draft.trim() && !imageDraft.items.length) || imageDraft.pending || state.phase !== 'ready'}
        onClick={() => void send()}>{state.phase === 'sending' ? '回复中' : '发送'}</Button>
    </View>
    {draft.length > 3600 ? <Text className={styles['composerHint'] ?? ''}>{draft.length}/4000</Text> : null}
  </View>
}
export default withMiniTestLogin(ChickenbroPage)
