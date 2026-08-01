import { useDidShow } from '@tarojs/taro'
import { useCallback, useState } from 'react'

import { taroStorage, wowApi } from '@wow-mini/api-client'
import { ActionButton } from '@wow-mini/design-system/components/ActionButton'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { ChickenbroComposer, ChickenbroTranscript } from '@wow-mini/design-system/components/ChickenbroChatComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { storageKey, type ChatMessage } from '@wow-mini/domain'

import { useTabRootIdentity } from '../../use-tab-root-identity'
import { navigateTo } from '../_shared/route-runtime'
import {
  boundedChickenbroMessage,
  chickenbroMarkMessageReceived,
  chickenbroTranscript,
  type ChickenbroInputState,
} from './chickenbro-model'
import styles from './simulator-home.module.scss'

const pendingSessionStorageKey = storageKey('chickenbro.pendingSessionId')

export default function SimulatorHomePage() {
  useTabRootIdentity('pages/simulator/simulator')
  const [messages, setMessages] = useState<readonly ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [inputState, setInputState] = useState<ChickenbroInputState>('idle')
  const [lastSubmitted, setLastSubmitted] = useState('')
  const [failedMessageId, setFailedMessageId] = useState('')
  const [restoreSessionId, setRestoreSessionId] = useState('')

  const restoreSession = useCallback(async (requestedSessionId: string) => {
    if (!requestedSessionId) return
    setRestoreSessionId(requestedSessionId)
    setInputState('loading')
    try {
      const result = await wowApi.simulator.chickenbroSession(requestedSessionId)
      if (result.fromFallback || !result.payload.session) {
        setInputState('error')
        return
      }
      setSessionId(result.payload.session.sessionId)
      setMessages(chickenbroTranscript(result.payload.messages))
      setDraft('')
      setLastSubmitted('')
      setFailedMessageId('')
      setRestoreSessionId('')
      setInputState('ready')
    } catch {
      setInputState('error')
    }
  }, [])

  useDidShow(() => {
    const selectedSessionId = taroStorage.get<string>(pendingSessionStorageKey)
    if (!selectedSessionId) return
    taroStorage.remove(pendingSessionStorageKey)
    void restoreSession(selectedSessionId)
  })

  const newTopic = () => {
    if (inputState === 'loading') return
    setMessages([])
    setDraft('')
    setSessionId('')
    setLastSubmitted('')
    setFailedMessageId('')
    setRestoreSessionId('')
    setInputState('idle')
  }

  const send = async (explicitMessage?: string) => {
    const message = boundedChickenbroMessage(explicitMessage ?? draft)
    if (!message || inputState === 'loading') return

    const localMessageId = `local-user-${Date.now()}`
    setMessages((current) => [...current, {
      messageId: localMessageId,
      role: 'user',
      content: message,
      status: 'sending',
    }])
    setDraft('')
    setLastSubmitted(message)
    setFailedMessageId('')
    setRestoreSessionId('')
    setInputState('loading')

    try {
      const result = await wowApi.simulator.message({
        message,
        ...(sessionId ? { sessionId } : {}),
      })
      if (result.fromFallback) {
        setFailedMessageId(localMessageId)
        setInputState('error')
        return
      }
      const assistant = result.payload.assistantMessage
      setSessionId(result.payload.session.sessionId)
      setMessages((current) => [
        ...chickenbroMarkMessageReceived(current, localMessageId),
        {
          ...assistant,
          messageId: assistant.messageId || `assistant-${Date.now()}`,
          status: 'received',
        },
      ])
      setInputState('ready')
    } catch {
      setFailedMessageId(localMessageId)
      setInputState('error')
    }
  }

  const retry = () => {
    if (inputState === 'loading') return
    if (restoreSessionId) {
      void restoreSession(restoreSessionId)
      return
    }
    if (!lastSubmitted) return
    if (failedMessageId) setMessages((current) => current.filter((message) => message.messageId !== failedMessageId))
    void send(lastSubmitted)
  }

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.captain-page-frame"
      tabRoot
      dock={(
        <RouteRegion className={styles['composerDock'] ?? ''} data-region="composer_dock">
          <ChickenbroComposer draft={draft} state={inputState} onDraftChange={setDraft} onSend={() => void send()} />
        </RouteRegion>
      )}
    >
      <RouteStage className={styles['pageFrame'] ?? ''} routeState={inputState} targetRegionCount={3} width="full">
        <PageFrame
          region="page_header"
          leftAction={(
            <ActionButton ariaLabel="查看对话存档" dataRole="chickenbro-open-archive" disabled={inputState === 'loading'} variant="ghost" onClick={() => navigateTo('/pages/simulator/chickenbro')}>
              对话存档
            </ActionButton>
          )}
          rightAction={(
            <ActionButton ariaLabel="新话题" dataRole="chickenbro-new-topic" disabled={inputState === 'loading'} variant="ghost" onClick={newTopic}>
              + 新话题
            </ActionButton>
          )}
          title="炸鸡队长"
          variant="simulator-home"
        >
          <RouteRegion className={styles['transcriptRegion'] ?? ''} data-region="captain_transcript">
            <ChickenbroTranscript messages={messages} state={inputState} onRetry={retry} />
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
