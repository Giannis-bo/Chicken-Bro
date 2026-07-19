import { View } from '@tarojs/components'
import { useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import {
  SimulatorCaptainAction,
  SimulatorComposer,
  SimulatorEvidenceShelf,
  SimulatorGuidancePanel,
  SimulatorTranscript,
} from '@wow-mini/design-system/components/SimulatorHomeComponents'
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

  const resetTopic = () => {
    setMessages(initialSimulatorHomeMessages())
    setDraft('')
    setSessionId('')
    setInputState('ready')
    setLastSubmitted('')
  }

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
      <RouteStage
        className={styles['pageFrame'] ?? ''}
        routeState={inputState}
        targetRegionCount={7}
        width="full"
      >
        <PageFrame
          region="header_bar"
          rightAction={(
            <SimulatorCaptainAction
              disabled={inputState === 'loading'}
              onReset={resetTopic}
            />
          )}
          title="智能分析"
          variant="simulator-home"
        >
          <RouteRegion className={styles['guidanceRegion'] ?? ''} data-region="simulator_guidance">
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
          </RouteRegion>
          <RouteRegion className={styles['transcriptRegion'] ?? ''} data-region="simulator_transcript">
            <SimulatorTranscript messages={messages} inputState={inputState} onRetry={retry} />
          </RouteRegion>
          <RouteRegion className={styles['evidenceRegion'] ?? ''} data-region="evidence_shelf">
            <SimulatorEvidenceShelf
              cards={evidenceCards}
              evidenceCount={context.evidenceCount}
              onManageEvidence={() => setDraft('请列出当前回答引用的证据、缺失输入和限制。')}
            />
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
