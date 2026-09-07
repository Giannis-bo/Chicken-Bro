import { MiniHelpActions } from '../../components/MiniHelp'
import { useTabRootIdentity } from '../../use-tab-root-identity'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import { Button, Image, ScrollView, Text, Textarea, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useEffect, useMemo, useRef, useState } from 'react'
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
  const [historyOpen, setHistoryOpen] = useState(false)
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
  useEffect(() => { if (isTestLoginEnabled()) void loginAndLoad() }, [model, sessions])
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
  }, [following, state.activeConversation, state.streamText, state.pendingUserContent])
  useEffect(() => () => { if (scrollTimer.current) clearTimeout(scrollTimer.current) }, [])
  useEffect(() => {
    setElapsed(0)
    if (state.phase !== 'sending') return
    const started = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [state.phase])

  const send = async () => {
    if (sending.current || busy || !draft.trim() || state.phase !== 'ready') return
    sending.current = true
    setPreparing(true)
    const content = draft.trim()
    try {
      if (!model.get().activeConversation) {
        const created = await model.create(content.slice(0, 32))
        if (!created || !mounted.current) return
      }
      const task = model.send(content)
      if (task) { setDraft(''); setFollowing(true) }
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
    if (busy) return
    if (draft.trim()) {
      const answer = await Taro.showModal({ title: '新建对话', content: '当前还有未发送的内容。新建后将清空输入框。', confirmText: '新建' })
      if (!answer.confirm || !mounted.current) return
    }
    setPreparing(true)
    try {
      const created = await model.create()
      if (created && mounted.current) { setDraft(''); setHistoryOpen(false); setFollowing(true) }
    } finally { if (mounted.current) setPreparing(false) }
  }

  return <View className={styles['page'] ?? ''} data-chat-phase={state.phase}>
    <View className={styles['header'] ?? ''}>
      <Button className={styles['historyButton'] ?? ''} disabled={busy} onClick={() => setHistoryOpen(!historyOpen)}>
        {historyOpen ? '收起历史 ▴' : '历史对话 ▾'}
      </Button>
      <Button className={styles['secondaryButton'] ?? ''} disabled={busy} onClick={() => void startNew()}>＋ 新对话</Button>
      <MiniHelpActions />
    </View>
    {historyOpen ? <ScrollView className={styles['history'] ?? ''} scrollY>
      {state.conversations.map((conversation, index) => <Button key={conversation.id}
        className={`${styles['conversationButton']} ${state.activeConversation?.id === conversation.id ? styles['activeConversation'] : ''}`}
        disabled={busy} onClick={() => {
          if (draft.trim()) { void Taro.showToast({ title: '请先发送或清空输入内容', icon: 'none' }); return }
          setHistoryOpen(false); setFollowing(true); void model.open(conversation.id)
        }}>
        <Text className={styles['conversationTitle'] ?? ''}>{conversation.title || `对话 ${state.conversations.length - index}`}</Text>
        <Text className={styles['conversationTime'] ?? ''}>{new Date(conversation.updatedAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</Text>
      </Button>)}
      {state.nextCursor ? <Button className={styles['secondaryButton'] ?? ''} disabled={busy} onClick={() => void model.loadMore()}>加载更多对话</Button> : null}
      {!state.conversations.length ? <Text className={styles['hint'] ?? ''}>还没有历史对话</Text> : null}
    </ScrollView> : null}
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
          <MiniMessage content={message.content} markdown={message.role !== 'user'} />
        </View>)}
        {state.pendingUserContent ? <View className={styles['userMessage'] ?? ''} data-persisted="false">
          <Text className={styles['messageRole'] ?? ''}>我</Text><MiniMessage content={state.pendingUserContent} />
        </View> : null}
        {state.phase === 'sending' ? <View className={styles['assistantMessage'] ?? ''} data-persisted="false">
          <View className={styles['messageRole'] ?? ''}>
            <Image className={styles['replyMascot'] ?? ''} src={mascot} mode="aspectFit" />
            <Text>鸡哥 · {state.streamText ? '正在回复' : `正在思考${elapsed >= 10 ? ` · ${elapsed} 秒` : '…'}`}</Text>
          </View>
          {state.streamText ? <MiniMessage content={state.streamText} markdown /> : <Text className={styles['hint'] ?? ''}>正在整理你的问题，查询日志或模拟可能需要一些时间。</Text>}
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
    <View className={styles['composer'] ?? ''}>
      <Textarea className={styles['textarea'] ?? ''} maxlength={4000} placeholder="发消息给鸡哥…" value={draft}
        autoHeight adjustPosition={false} holdKeyboard confirmType="send" showConfirmBar={false}
        disabled={preparing} onConfirm={() => void send()} onInput={(event) => setDraft(event.detail.value)} />
      <Button className={styles['sendButton'] ?? ''} disabled={busy || !draft.trim() || state.phase !== 'ready'}
        loading={busy && state.phase === 'sending'} onClick={() => void send()}>{state.phase === 'sending' ? '回复中' : '发送'}</Button>
    </View>
    {draft.length > 3600 ? <Text className={styles['composerHint'] ?? ''}>{draft.length}/4000</Text> : null}
  </View>
}
export default withMiniTestLogin(ChickenbroPage)
