import { Button, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'

import { ChatModel, type ChatModelState } from '../features/chat/chat-model'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>

const quickPrompts = [
  '帮我看看元素萨满的装备',
  '从一个模拟开始',
  '聊聊咕咕的新皮肤',
]

export interface WebChatViewProps {
  auth: WebClientAuth
  showHordeSkin?: boolean
}

export default function WebChatView({ auth, showHordeSkin = true }: WebChatViewProps) {
  const model = useMemo(() => new ChatModel(wowApi.chat, () => auth), [auth])
  const [state, setState] = useState<ChatModelState>(() => model.get())
  const [draft, setDraft] = useState('')
  const [petRun, setPetRun] = useState(0)

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
        <View className={styles['chatHeading'] ?? ''}>
          <View className={styles['chatTitleGroup'] ?? ''}>
            <Text className={styles['viewTitle'] ?? ''}>咕咕助手</Text>
            <Text className={styles['chatStatus'] ?? ''}>
              <Text className={styles['chatStatusDot'] ?? ''} />
              在线
            </Text>
          </View>
          <Text className={styles['chatSubtitle'] ?? ''}>先聊清楚，再一起行动</Text>
        </View>
        <Button
          className={styles['secondaryButton'] ?? ''}
          size="mini"
          disabled={state.phase === 'loading' || state.phase === 'sending'}
          onClick={() => void model.create()}
        >
          新对话
        </Button>
      </View>

      <View className={styles['splitView'] ?? ''}>
        <View className={styles['historyColumn'] ?? ''}>
          <ScrollView className={styles['sideList'] ?? ''} scrollY>
            <View className={styles['sideListIntro'] ?? ''}>
              <View className={styles['sideListIntroMascot'] ?? ''} />
              <View>
                <Text className={styles['sideListIntroTitle'] ?? ''}>历史对话</Text>
                <Text className={styles['sideListIntroMeta'] ?? ''}>服务端同步</Text>
              </View>
            </View>
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

          {showHordeSkin ? (
            <View className={styles['sideListPet'] ?? ''} key={petRun}>
              <Button
                className={styles['petButton'] ?? ''}
                onClick={() => setPetRun((current) => current + 1)}
              >
                <View className={styles['petMascot'] ?? ''} />
              </Button>
              <Text className={styles['petCaption'] ?? ''}>咕咕 · 远眺中</Text>
            </View>
          ) : null}
        </View>

        <View className={styles['chatPane'] ?? ''}>
          <ScrollView className={styles['messageList'] ?? ''} scrollY scrollIntoView="web-chat-end">
            {state.activeConversation?.messages.map((message) => (
              <View
                key={message.id}
                className={styles[message.role === 'user' ? 'webUserMessage' : 'webAssistantMessage'] ?? ''}
                data-message-id={message.id}
                data-persisted="true"
              >
                <Text className={styles['messageRole'] ?? ''}>{message.role === 'user' ? '你' : '咕咕'}</Text>
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
                <Text className={styles['messageRole'] ?? ''}>咕咕 · 生成中</Text>
                <Text className={styles['messageText'] ?? ''}>{state.streamText}</Text>
              </View>
            ) : null}
            {!state.activeConversation && state.phase === 'ready' ? (
              <View className={styles['emptyState'] ?? ''}>
                <Text className={styles['emptyEyebrow'] ?? ''}>WOW COMPANION / 对话</Text>
                <Text className={styles['emptyTitle'] ?? ''}>准备好了，随时开始</Text>
                <Text className={styles['emptyDescription'] ?? ''}>
                  把你的副本目标、装备疑问或输出困惑交给咕咕，先聊清楚再行动。
                </Text>
                <View className={styles['emptyHint'] ?? ''}>
                  <View className={styles['emptyHintDot'] ?? ''} />
                  <Text>创建一个新对话，就从这里开始</Text>
                </View>
              </View>
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
            <View className={styles['composerRow'] ?? ''}>
              <Text className={styles['composerAdd'] ?? ''}>＋</Text>
              <Textarea
                className={styles['webTextarea'] ?? ''}
                maxlength={4000}
                placeholder="问问咕咕"
                value={draft}
                onInput={(event) => setDraft(event.detail.value)}
              />
              <Text className={styles['composerMode'] ?? ''}>对话⌄</Text>
              <Button
                className={styles['primaryButton'] ?? ''}
                disabled={!draft.trim() || !state.activeConversation || state.phase === 'sending'}
                loading={state.phase === 'sending'}
                onClick={send}
              >
                ↑
              </Button>
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
            <Text className={styles['composerFootnote'] ?? ''}>咕咕可能会犯错，请核对重要信息。</Text>
          </View>
        </View>
      </View>
    </View>
  )
}
