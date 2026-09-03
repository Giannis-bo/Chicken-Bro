import { Button, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { useDidShow } from '@tarojs/taro'
import { useEffect, useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { ChatModel, type ChatModelState } from '../../features/chat/chat-model'
import styles from './index.module.scss'


export default function ChickenbroPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new ChatModel(wowApi.chat, () => sessions.createAuthContext()),
    [sessions],
  )
  const [state, setState] = useState<ChatModelState>(() => model.get())
  const [draft, setDraft] = useState('')

  useEffect(() => {
    const unsubscribe = model.subscribe(setState)
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model])

  const loginAndLoad = async () => {
    try {
      if (!sessions.getValid()) await sessions.login()
      await model.load()
    } catch {
      await model.recover()
    }
  }

  useDidShow(() => {
    void loginAndLoad()
  })

  const send = () => {
    const task = model.send(draft)
    if (task) setDraft('')
  }

  const retry = () => {
    if (state.phase === 'signed_out') {
      void sessions.logout().catch(() => undefined).finally(() => loginAndLoad())
      return
    }
    void model.recover()
  }

  return (
    <View className={styles['page'] ?? ''} data-chat-phase={state.phase}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>CHICKENBRO</Text>
          <Text className={styles['title'] ?? ''}>炸鸡队长</Text>
        </View>
        <Button
          className={styles['secondaryButton'] ?? ''}
          size="mini"
          onClick={() => void model.create()}
        >
          新会话
        </Button>
      </View>

      <ScrollView className={styles['conversationRail'] ?? ''} scrollX>
        <View className={styles['conversationRow'] ?? ''}>
          {state.conversations.map((conversation) => (
            <Button
              key={conversation.id}
              className={styles['conversationButton'] ?? ''}
              data-active={state.activeConversation?.id === conversation.id ? 'true' : 'false'}
              onClick={() => void model.open(conversation.id)}
            >
              {conversation.title || '炸鸡队长对话'}
            </Button>
          ))}
          {state.nextCursor ? (
            <Button className={styles['conversationButton'] ?? ''} onClick={() => void model.loadMore()}>
              更多
            </Button>
          ) : null}
        </View>
      </ScrollView>

      <ScrollView className={styles['messages'] ?? ''} scrollY scrollIntoView="chat-end">
        {state.activeConversation?.messages.map((message) => (
          <View
            key={message.id}
            className={styles[message.role === 'user' ? 'userMessage' : 'assistantMessage'] ?? ''}
            data-persisted="true"
          >
            <Text className={styles['messageRole'] ?? ''}>
              {message.role === 'user' ? '我' : '队长'}
            </Text>
            <Text className={styles['messageContent'] ?? ''}>{message.content}</Text>
          </View>
        ))}

        {state.pendingUserContent ? (
          <View className={styles['pendingMessage'] ?? ''} data-persisted="false">
            <Text className={styles['messageRole'] ?? ''}>发送中</Text>
            <Text className={styles['messageContent'] ?? ''}>{state.pendingUserContent}</Text>
          </View>
        ) : null}
        {state.streamText ? (
          <View className={styles['streamMessage'] ?? ''} data-persisted="false">
            <Text className={styles['messageRole'] ?? ''}>队长 · 生成中</Text>
            <Text className={styles['messageContent'] ?? ''}>{state.streamText}</Text>
          </View>
        ) : null}
        {!state.activeConversation && state.phase === 'ready' ? (
          <View className={styles['empty'] ?? ''}>
            <Text>还没有会话。新建一段对话，队长会把历史保存在服务端。</Text>
          </View>
        ) : null}
        <View id="chat-end" />
      </ScrollView>

      {state.phase === 'blocked' || state.phase === 'signed_out' ? (
        <View className={styles['errorCard'] ?? ''} data-error-code={state.errorCode}>
          <Text>{state.errorMessage || '会话暂不可用'}</Text>
          <Button className={styles['retryButton'] ?? ''} size="mini" onClick={retry}>
            {state.phase === 'signed_out' ? '重新登录' : '重新读取历史'}
          </Button>
        </View>
      ) : null}

      <View className={styles['composer'] ?? ''}>
        <Textarea
          className={styles['textarea'] ?? ''}
          maxlength={4000}
          placeholder="告诉队长你想分析什么…"
          value={draft}
          onInput={(event) => setDraft(event.detail.value)}
        />
        <Button
          className={styles['sendButton'] ?? ''}
          disabled={state.phase === 'sending' || !draft.trim() || !state.activeConversation}
          loading={state.phase === 'sending'}
          onClick={send}
        >
          发送
        </Button>
      </View>
    </View>
  )
}
