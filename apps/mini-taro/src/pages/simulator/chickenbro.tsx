import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import {
  AppShell,
  ChickenbroAnswerStatePanel,
  ChickenbroAssistantTurnSlot,
  ChickenbroComposer,
  ChickenbroContextPanel,
  ChickenbroEvidenceAnswer,
  ChickenbroEvidenceBoundary,
  ChickenbroIntroMessage,
  ChickenbroTopicLibrary,
  ChickenbroUserTurnSlot,
  PageFrame,
} from '@wow-mini/design-system'
import type { ChatMessage } from '@wow-mini/domain'

import { goBack, safeDecode } from '../_shared/route-runtime'
import {
  boundedChickenbroMessage,
  chickenbroAnswerSource,
  chickenbroConfidence,
  chickenbroContextLabel,
  chickenbroEvidenceRows,
  chickenbroIntro,
  chickenbroLatestPayload,
  chickenbroLimitations,
  chickenbroMissingInputs,
  chickenbroScenarioLabel,
  chickenbroTopicPrompts,
  chickenbroVisibleTurns,
  type ChickenbroContextValue,
} from './chickenbro-model'
import styles from './chickenbro.module.scss'

type InputState = 'idle' | 'loading' | 'ready' | 'error'

export default function ChickenbroPage() {
  const router = useRouter()
  const context: ChickenbroContextValue = {
    from: safeDecode(router.params['from']),
    classKey: safeDecode(router.params['classKey']),
    specKey: safeDecode(router.params['specKey']),
    spec: safeDecode(router.params['spec']),
    scenario: safeDecode(router.params['scenario']),
  }
  const [messages, setMessages] = useState<readonly ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [inputState, setInputState] = useState<InputState>('idle')
  const [lastSubmitted, setLastSubmitted] = useState('')
  const [transportError, setTransportError] = useState('')

  const send = async (explicitMessage?: string, appendUser = true) => {
    const message = boundedChickenbroMessage(explicitMessage ?? draft)
    if (!message || inputState === 'loading') return
    setLastSubmitted(message)
    setDraft('')
    setInputState('loading')
    setTransportError('')
    if (appendUser) {
      const userMessage: ChatMessage = {
        messageId: `local-user-${Date.now()}`,
        role: 'user',
        content: message,
        status: '等待后端回答',
      }
      setMessages((current) => [...current, userMessage].slice(-80))
    }
    try {
      const result = await wowApi.simulator.message({
        message,
        sessionId,
        mode: 'chickenbro',
        context,
      })
      if (result.fromFallback) {
        setTransportError(result.error || '后端暂时不可用；没有生成本地替代回答。')
        setInputState('error')
        return
      }
      const assistant = result.payload.assistantMessage
      setSessionId(result.payload.session.sessionId || sessionId)
      setMessages((current) => [...current, {
        ...assistant,
        messageId: assistant.messageId || `assistant-${Date.now()}`,
        status: assistant.status || '后端已返回',
      }].slice(-80))
      setInputState('ready')
    } catch (error) {
      setTransportError(error instanceof Error ? error.message : '后端请求失败')
      setInputState('error')
    }
  }

  const reset = () => {
    setMessages([])
    setDraft('')
    setSessionId('')
    setLastSubmitted('')
    setTransportError('')
    setInputState('idle')
  }

  const turns = chickenbroVisibleTurns(messages)
  const primaryTurn = turns[0]
  const followupTurn = turns[1]
  const primaryEvidenceRefs = primaryTurn?.assistant?.payload?.evidenceRefs ?? []
  const payload = chickenbroLatestPayload(messages)
  const prompts = chickenbroTopicPrompts(context)
  const evidenceCount = payload?.evidenceRefs.length ?? 0
  const evidenceLabel = payload
    ? evidenceCount
      ? `${evidenceCount} 条后端引用`
      : payload.confidence === 'blocked' ? '回答已阻断' : '待补证据'
    : '尚未返回'
  const answerState = inputState === 'loading'
    ? { title: '正在等待后端回答', detail: '最长等待 90 秒，不生成本地结论' }
    : inputState === 'error'
      ? { title: '暂时无法生成回答', detail: transportError || '可以重试最后一条真实问题' }
      : inputState === 'ready'
        ? { title: '后端已返回受限回答', detail: `${chickenbroAnswerSource(payload)} · ${chickenbroConfidence(payload)}` }
        : { title: '等待你的问题', detail: '只解释证据，缺资料时先给下一步' }

  const inspectEvidence = () => {
    if (!primaryEvidenceRefs.length) return
    void Taro.showModal({
      title: '后端证据引用',
      content: primaryEvidenceRefs.join('\n').slice(0, 1800),
      showCancel: false,
    })
  }

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.chickenbro-page-frame"
      dock={(
        <View className={styles['composerDock'] ?? ''}>
          <ChickenbroComposer
            draft={draft}
            state={inputState}
            onDraftChange={setDraft}
            onNewTopic={reset}
            onSend={() => void send()}
          />
        </View>
      )}
    >
      <View className={styles['pageFrame'] ?? ''} data-route-state={inputState} data-target-region-count="12">
        <PageFrame
          backRegion="chickenbro-chat-back"
          region="header_nav"
          title="炸鸡队长"
          variant="chickenbro-chat"
          onBack={() => goBack('/pages/simulator/simulator')}
        >
          <View className={styles['contextRegion'] ?? ''}>
            <ChickenbroContextPanel
              cells={[
                { id: 'specialization', label: '职业 / 专精', value: chickenbroContextLabel(context) },
                { id: 'scenario', label: '场景', value: chickenbroScenarioLabel(context) },
                { id: 'evidence', label: '资料状态', value: evidenceLabel },
              ]}
              evidenceLabel={evidenceLabel}
              onOpenWorkbench={() => goBack('/pages/builds/workbench')}
            />
          </View>
          <View className={styles['introRegion'] ?? ''}>
            <ChickenbroIntroMessage content={chickenbroIntro(context)} />
          </View>
          <View className={styles['primaryUserRegion'] ?? ''}>
            <ChickenbroUserTurnSlot message={primaryTurn?.user} region="user_question_primary" />
          </View>
          <View className={styles['answerRegion'] ?? ''}>
            <ChickenbroEvidenceAnswer
              confidenceLabel={chickenbroConfidence(primaryTurn?.assistant?.payload)}
              evidenceCount={primaryTurn?.assistant?.payload?.evidenceRefs.length ?? 0}
              evidenceRows={chickenbroEvidenceRows(primaryTurn?.assistant?.payload)}
              message={primaryTurn?.assistant}
              sourceLabel={chickenbroAnswerSource(primaryTurn?.assistant?.payload)}
              onInspectEvidence={inspectEvidence}
            />
          </View>
          <View className={styles['boundaryRegion'] ?? ''}>
            <ChickenbroEvidenceBoundary
              helper={payload?.nextQuestion || '等待后端说明下一步'}
              limitations={chickenbroLimitations(payload)}
              missingInputs={chickenbroMissingInputs(payload)}
            />
          </View>
          <View className={styles['followupUserRegion'] ?? ''}>
            <ChickenbroUserTurnSlot message={followupTurn?.user} region="user_question_followup" />
          </View>
          <View className={styles['followupAnswerRegion'] ?? ''}>
            <ChickenbroAssistantTurnSlot message={followupTurn?.assistant} />
          </View>
          <View className={styles['answerStateRegion'] ?? ''}>
            <ChickenbroAnswerStatePanel
              canRetry={inputState === 'error' && Boolean(lastSubmitted)}
              detail={answerState.detail}
              state={inputState}
              title={answerState.title}
              onRetry={() => void send(lastSubmitted, false)}
            />
          </View>
          <View className={styles['topicRegion'] ?? ''}>
            <ChickenbroTopicLibrary prompts={prompts} onSelect={(index) => setDraft(prompts[index] ?? '')} />
          </View>
        </PageFrame>
      </View>
    </AppShell>
  )
}
