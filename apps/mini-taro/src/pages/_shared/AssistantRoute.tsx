import { View } from '@tarojs/components'
import { useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import {
  ActionButton,
  AppShell,
  ChatShell,
  EvidenceLedger,
  PageFrame,
  WowPanel,
  type EvidenceLedgerRow,
} from '@wow-mini/design-system'
import type { ChatMessage, ReadinessState } from '@wow-mini/domain'

import { goBack } from './route-runtime'
import styles from './routes.module.scss'

export interface AssistantContext {
  from?: string
  classKey?: string
  specKey?: string
  spec?: string
  scenario?: string
}

export interface AssistantRouteProps {
  tabRoot?: boolean
  context?: AssistantContext
}

function contextLabel(context: AssistantContext | undefined): string {
  if (!context) return ''
  return [context.spec, context.classKey, context.specKey, context.scenario].filter(Boolean).join(' · ')
}

function initialMessage(context: AssistantContext | undefined): ChatMessage {
  const label = contextLabel(context)
  return {
    messageId: 'assistant-welcome',
    role: 'assistant',
    content: label
      ? `已带入 ${label} 的工作台上下文。你可以追问阻断、来源或下一步；缺少证据时我只说明缺什么。`
      : '请描述职业、专精、场景和问题。缺少 SimC、日志或来源证据时，我不会编造 DPS、排名或结论。',
    status: label ? '工作台上下文' : '证据边界开启',
  }
}

function suggestions(context: AssistantContext | undefined): readonly string[] {
  return contextLabel(context)
    ? ['当前最大的阻断是什么？', '这些结论分别来自哪里？', '下一步应该补什么证据？']
    : ['帮我检查 SimC 前还缺什么', '如何整理可验证的天赋和装备上下文？', '解释一条来源证据的边界']
}

export function AssistantRoute({ tabRoot = false, context }: AssistantRouteProps) {
  const [messages, setMessages] = useState<readonly ChatMessage[]>([initialMessage(context)])
  const [draft, setDraft] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [inputState, setInputState] = useState<Extract<ReadinessState, 'ready' | 'loading' | 'blocked' | 'error' | 'unknown'>>('ready')
  const [lastSubmitted, setLastSubmitted] = useState('')

  const send = async (explicitMessage?: string) => {
    const message = (explicitMessage ?? draft).trim().slice(0, 2000)
    if (!message || inputState === 'loading') return
    setLastSubmitted(message)
    setDraft('')
    setInputState('loading')
    const userMessage: ChatMessage = {
      messageId: `local-user-${Date.now()}`,
      role: 'user',
      content: message,
      status: '发送中',
    }
    setMessages((current) => [...current, userMessage].slice(-80))
    const result = await wowApi.simulator.message({
      message,
      sessionId,
      mode: 'chickenbro',
      context: context ?? {},
    })
    const assistant = result.payload.assistantMessage
    setSessionId(result.payload.session.sessionId || sessionId)
    setMessages((current) => [...current, {
      ...assistant,
      messageId: assistant.messageId || `assistant-${Date.now()}`,
      status: result.fromFallback ? '后端不可用 · 回退说明' : assistant.status || '已完成',
    }].slice(-80))
    setInputState(result.fromFallback ? 'error' : 'ready')
  }

  const reset = () => {
    setMessages([initialMessage(context)])
    setSessionId('')
    setDraft('')
    setLastSubmitted('')
    setInputState('ready')
  }

  const ledger: readonly EvidenceLedgerRow[] = [
    {
      id: 'context', label: '工作台上下文',
      value: contextLabel(context) || '未带入职业与专精上下文',
      state: contextLabel(context) ? 'source_reference' : 'unknown',
    },
    {
      id: 'answer', label: '回答来源',
      value: '由后端返回；前端回退只说明服务不可用，不生成结论。',
      state: inputState === 'error' ? 'blocked' : 'source_reference',
    },
  ]

  return (
    <AppShell tabRoot={tabRoot}>
      <PageFrame
        kicker="证据教练"
        rightAction={<ActionButton variant="ghost" onClick={reset}>新话题</ActionButton>}
        title="炸鸡队长"
        {...(tabRoot ? {} : { onBack: () => goBack('/pages/simulator/simulator') })}
      >
        <ChatShell
          context={(
            <View className={styles['section'] ?? ''}>
              <WowPanel description="快捷问题只填入输入，不代表已有结论。" title={contextLabel(context) || '开始提问'}>
                <View className={styles['actions'] ?? ''}>
                  {suggestions(context).map((prompt) => (
                    <ActionButton key={prompt} variant="secondaryMetal" onClick={() => setDraft(prompt)}>{prompt}</ActionButton>
                  ))}
                </View>
              </WowPanel>
              <WowPanel title="证据边界"><EvidenceLedger rows={ledger} /></WowPanel>
            </View>
          )}
          draft={draft}
          inputState={inputState}
          messages={messages}
          showTopicDrawerGlyph={!tabRoot}
          tabRoot={tabRoot}
          onDraftChange={setDraft}
          onRetry={() => void send(lastSubmitted)}
          onSend={() => void send()}
        />
      </PageFrame>
    </AppShell>
  )
}
