import { Button, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'

import { ChatModel, type ChatModelState } from '../features/chat/chat-model'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>

export interface WebChatViewProps {
  auth: WebClientAuth
}

export default function WebChatView({ auth }: WebChatViewProps) {
  const model = useMemo(() => new ChatModel(wowApi.chat, () => auth), [auth])
  const [state, setState] = useState<ChatModelState>(() => model.get())
  const [draft, setDraft] = useState('')

  useEffect(() => {
    const unsubscribe = model.subscribe(setState)
    void model.load()
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model])

  const send = () => {
    const task = model.send(draft)
    if (task) setDraft('')
  }

  return (
    <View className={styles['businessView'] ?? ''} data-chat-phase={state.phase}>
      <View className={styles['viewHeader'] ?? ''}>
        <View>
          <Text className={styles['viewEyebrow'] ?? ''}>CHICKENBRO</Text>
          <Text className={styles['viewTitle'] ?? ''}>炸鸡队长</Text>
        </View>
        <Button
          className={styles['primaryButton'] ?? ''}
          size="mini"
          disabled={state.phase === 'loading' || state.phase === 'sending'}
          onClick={() => void model.create()}
        >
          新会话
        </Button>
      </View>

      <View className={styles['splitView'] ?? ''}>
        <ScrollView className={styles['sideList'] ?? ''} scrollY>
          {state.conversations.map((conversation) => (
            <Button
              key={conversation.id}
              className={styles['sideListButton'] ?? ''}
              data-active={state.activeConversation?.id === conversation.id ? 'true' : 'false'}
              onClick={() => void model.open(conversation.id)}
            >
              <Text>{conversation.title || '炸鸡队长对话'}</Text>
              <Text className={styles['listMeta'] ?? ''}>{conversation.updatedAt}</Text>
            </Button>
          ))}
          {state.nextCursor ? (
            <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.loadMore()}>
              加载更多
            </Button>
          ) : null}
          {!state.conversations.length && state.phase === 'ready' ? (
            <Text className={styles['emptyCopy'] ?? ''}>还没有服务端会话。</Text>
          ) : null}
        </ScrollView>

        <View className={styles['chatPane'] ?? ''}>
          <ScrollView className={styles['messageList'] ?? ''} scrollY scrollIntoView="web-chat-end">
            {state.activeConversation?.messages.map((message) => (
              <View
                key={message.id}
                className={styles[message.role === 'user' ? 'webUserMessage' : 'webAssistantMessage'] ?? ''}
                data-message-id={message.id}
                data-persisted="true"
              >
                <Text className={styles['messageRole'] ?? ''}>{message.role === 'user' ? '我' : '队长'}</Text>
                <Text className={styles['messageText'] ?? ''}>{message.content}</Text>
              </View>
            ))}
            {state.pendingUserContent ? (
              <View className={styles['webUserMessage'] ?? ''} data-persisted="false">
                <Text className={styles['messageRole'] ?? ''}>发送中</Text>
                <Text className={styles['messageText'] ?? ''}>{state.pendingUserContent}</Text>
              </View>
            ) : null}
            {state.streamText ? (
              <View className={styles['webAssistantMessage'] ?? ''} data-persisted="false">
                <Text className={styles['messageRole'] ?? ''}>队长 · 生成中</Text>
                <Text className={styles['messageText'] ?? ''}>{state.streamText}</Text>
              </View>
            ) : null}
            {!state.activeConversation && state.phase === 'ready' ? (
              <Text className={styles['emptyCopy'] ?? ''}>新建会话后，双端会读取同一份服务端历史。</Text>
            ) : null}
            <View id="web-chat-end" />
          </ScrollView>

          {state.phase === 'blocked' || state.phase === 'signed_out' ? (
            <View className={styles['inlineError'] ?? ''} data-error-code={state.errorCode}>
              <Text>{state.phase === 'signed_out' ? 'Web 登录已失效，请重新扫码登录' : state.errorMessage}</Text>
              <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.recover()}>
                重新读取历史
              </Button>
            </View>
          ) : null}

          <View className={styles['webComposer'] ?? ''}>
            <Textarea
              className={styles['webTextarea'] ?? ''}
              maxlength={4000}
              placeholder="告诉队长你想分析什么…"
              value={draft}
              onInput={(event) => setDraft(event.detail.value)}
            />
            <Button
              className={styles['primaryButton'] ?? ''}
              disabled={!draft.trim() || !state.activeConversation || state.phase === 'sending'}
              loading={state.phase === 'sending'}
              onClick={send}
            >
              发送
            </Button>
          </View>
        </View>
      </View>
    </View>
  )
}
