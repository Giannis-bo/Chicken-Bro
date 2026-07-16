import { View } from '@tarojs/components'
import { useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import {
  AppShell,
  PageFrame,
  SimulatorComposer,
  SimulatorEvidenceShelf,
  SimulatorGuidancePanel,
  SimulatorTranscript,
} from '@wow-mini/design-system'
import type { ChatMessage } from '@wow-mini/domain'

import {
  initialSimulatorHomeMessages,
  simulatorAssistantStatus,
  simulatorEvidenceCards,
  simulatorHomeContext,
  simulatorHomeSuggestions,
  type SimulatorHomeInputState,
} from './simulator-home-model'
import styles from './simulator-home.module.scss'

function updateMessageStatus(
  messages: readonly ChatMessage[],
  messageId: string,
  status: string,
): readonly ChatMessage[] {
  return messages.map((message) => message.messageId === messageId ? { ...message, status } : message)
}

export default function SimulatorHomePage() {
  const [messages, setMessages] = useState<readonly ChatMessage[]>(initialSimulatorHomeMessages)
  const [draft, setDraft] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [inputState, setInputState] = useState<SimulatorHomeInputState>('ready')
  const [lastSubmitted, setLastSubmitted] = useState('')

  const context = useMemo(() => simulatorHomeContext(messages), [messages])
  const evidenceCards = useMemo(() => simulatorEvidenceCards(messages), [messages])

  const send = async (explicitMessage?: string) => {
    const message = (explicitMessage ?? draft).trim().slice(0, 2000)
    if (!message || inputState === 'loading') return

    const localMessageId = `local-user-${Date.now()}`
    const userMessage: ChatMessage = {
      messageId: localMessageId,
      role: 'user',
      content: message,
      status: '等待后端',
    }
    setLastSubmitted(message)
    setDraft('')
    setInputState('loading')
    setMessages((current) => [...current, userMessage].slice(-80))

    try {
      const result = await wowApi.simulator.message({
        message,
        sessionId,
        mode: 'chickenbro',
        context: {},
      })

      if (result.fromFallback) {
        setMessages((current) => updateMessageStatus(current, localMessageId, '发送失败 · 可重试'))
        setInputState('error')
        return
      }

      const assistant = result.payload.assistantMessage
      setSessionId(result.payload.session.sessionId || sessionId)
      setMessages((current) => [
        ...updateMessageStatus(current, localMessageId, '已提交'),
        {
          ...assistant,
          messageId: assistant.messageId || `assistant-${Date.now()}`,
          status: simulatorAssistantStatus(assistant, false),
        },
      ].slice(-80))
      setInputState('ready')
    } catch {
      setMessages((current) => updateMessageStatus(current, localMessageId, '发送失败 · 可重试'))
      setInputState('error')
    }
  }

  const retry = () => {
    if (!lastSubmitted || inputState === 'loading') return
    setMessages((current) => current.filter((message) => (
      message.messageId !== 'assistant-transport-error'
      && !(message.role === 'user' && message.status === '发送失败 · 可重试')
    )))
    void send(lastSubmitted)
  }

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.simulator-page-frame"
      tabRoot
      dock={(
        <View className={styles['composerDock'] ?? ''}>
          <SimulatorComposer
            draft={draft}
            inputState={inputState}
            onDraftChange={setDraft}
            onRetry={retry}
            onSend={() => void send()}
          />
        </View>
      )}
    >
      <View
        className={styles['pageFrame'] ?? ''}
        data-route-state={inputState}
        data-target-region-count="7"
      >
        <PageFrame
          region="header_bar"
          title="智能分析"
          variant="simulator-home"
        >
          <View className={styles['guidanceRegion'] ?? ''}>
            <SimulatorGuidancePanel
              answerSourceLabel={context.answerSourceLabel}
              confidenceLabel={context.confidenceLabel}
              evidenceCount={context.evidenceCount}
              evidenceStateLabel={context.evidenceStateLabel}
              limitations={context.limitations}
              missingInputs={context.missingInputs}
              suggestions={simulatorHomeSuggestions}
              onManageEvidence={() => setDraft('请列出当前回答引用的证据、缺失输入和限制。')}
              onSuggestion={setDraft}
            />
          </View>
          <View className={styles['transcriptRegion'] ?? ''}>
            <SimulatorTranscript messages={messages} inputState={inputState} onRetry={retry} />
          </View>
          <View className={styles['evidenceRegion'] ?? ''}>
            <SimulatorEvidenceShelf
              cards={evidenceCards}
              evidenceCount={context.evidenceCount}
              onManageEvidence={() => setDraft('请列出当前回答引用的证据、缺失输入和限制。')}
            />
          </View>
        </PageFrame>
      </View>
    </AppShell>
  )
}
