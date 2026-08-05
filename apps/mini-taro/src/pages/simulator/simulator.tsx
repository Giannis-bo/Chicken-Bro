import { useDidShow } from '@tarojs/taro'
import { useCallback, useEffect, useRef, useState } from 'react'

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
  chickenbroAppendStreamDelta,
  chickenbroClearStream,
  chickenbroFollowFromDistance,
  chickenbroMarkMessageReceived,
  chickenbroNoteIncoming,
  chickenbroResumeLatest,
  chickenbroStartStream,
  chickenbroTranscript,
  type ChickenbroStreamState,
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
  const [streamState, setStreamState] = useState<ChickenbroStreamState>(() => chickenbroClearStream(chickenbroStartStream('initial')))
  const [scrollTop, setScrollTop] = useState(0)
  const streamStateRef = useRef<ChickenbroStreamState>(chickenbroClearStream(chickenbroStartStream('initial')))
  const streamTaskRef = useRef<{ abort: () => void } | null>(null)
  const streamGenerationRef = useRef(0)
  const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const updateStreamState = useCallback((next: ChickenbroStreamState) => {
    streamStateRef.current = next
    setStreamState(next)
  }, [])

  const queueScrollToLatest = useCallback(() => {
    if (scrollTimerRef.current) return
    scrollTimerRef.current = setTimeout(() => {
      scrollTimerRef.current = null
      setScrollTop((current) => current + 1000000)
    }, 0)
  }, [])

  const abortActiveStream = useCallback(() => {
    streamGenerationRef.current += 1
    streamTaskRef.current?.abort()
    streamTaskRef.current = null
    updateStreamState(chickenbroClearStream(streamStateRef.current))
  }, [updateStreamState])

  useEffect(() => () => {
    streamGenerationRef.current += 1
    streamTaskRef.current?.abort()
    if (scrollTimerRef.current) clearTimeout(scrollTimerRef.current)
  }, [])

  const restoreSession = useCallback(async (requestedSessionId: string) => {
    if (!requestedSessionId) return
    abortActiveStream()
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
      updateStreamState(chickenbroClearStream(chickenbroStartStream('restored')))
      queueScrollToLatest()
      setInputState('ready')
    } catch {
      setInputState('error')
    }
  }, [abortActiveStream, queueScrollToLatest, updateStreamState])

  useDidShow(() => {
    const selectedSessionId = taroStorage.get<string>(pendingSessionStorageKey)
    if (!selectedSessionId) return
    taroStorage.remove(pendingSessionStorageKey)
    void restoreSession(selectedSessionId)
  })

  const newTopic = () => {
    abortActiveStream()
    setMessages([])
    setDraft('')
    setSessionId('')
    setLastSubmitted('')
    setFailedMessageId('')
    setRestoreSessionId('')
    updateStreamState(chickenbroClearStream(chickenbroStartStream('new-topic')))
    setInputState('idle')
  }

  const send = (explicitMessage?: string) => {
    const message = boundedChickenbroMessage(explicitMessage ?? draft)
    if (!message || inputState === 'loading') return

    abortActiveStream()
    const requestGeneration = streamGenerationRef.current + 1
    streamGenerationRef.current = requestGeneration
    const localMessageId = `local-user-${Date.now()}-${requestGeneration}`
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

    const failCurrentMessage = () => {
      if (streamGenerationRef.current !== requestGeneration) return
      updateStreamState(chickenbroClearStream(streamStateRef.current))
      setFailedMessageId(localMessageId)
      setInputState('error')
    }
    const acceptFinalResponse = (result: Awaited<ReturnType<typeof wowApi.simulator.message>>) => {
      if (streamGenerationRef.current !== requestGeneration) return
      if (result.fromFallback) {
        failCurrentMessage()
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
      const beforeFinal = chickenbroNoteIncoming(streamStateRef.current)
      const clearedStream = chickenbroClearStream(beforeFinal)
      const nextStreamState = beforeFinal.followLatest ? clearedStream : { ...clearedStream, hasUnseen: true }
      updateStreamState(nextStreamState)
      if (nextStreamState.followLatest) queueScrollToLatest()
      setInputState('ready')
    }
    const task = wowApi.simulator.streamMessage(
      {
        message,
        ...(sessionId ? { sessionId } : {}),
        clientMessageId: localMessageId,
      },
      {
        onEvent: (event) => {
          if (streamGenerationRef.current !== requestGeneration) return
          if (event.type === 'started') {
            updateStreamState(chickenbroStartStream(event.requestId))
            setSessionId(event.sessionId)
            queueScrollToLatest()
            return
          }
          if (event.type === 'status') return
          if (event.type === 'delta') {
            const appended = chickenbroAppendStreamDelta(streamStateRef.current, event.requestId, event.sequence, event.text)
            if (!appended.accepted) {
              streamTaskRef.current?.abort()
              failCurrentMessage()
              return
            }
            const nextStreamState = chickenbroNoteIncoming(appended.state)
            updateStreamState(nextStreamState)
            if (nextStreamState.followLatest) queueScrollToLatest()
            return
          }
          if (event.type === 'final') {
            acceptFinalResponse({ payload: event.response, fromFallback: false, error: '' })
            return
          }
          failCurrentMessage()
        },
        onFailure: failCurrentMessage,
        onFallback: acceptFinalResponse,
      },
    )
    if (streamGenerationRef.current === requestGeneration) streamTaskRef.current = task
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
      bodyScrollable={false}
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
            <ActionButton ariaLabel="新话题" dataRole="chickenbro-new-topic" variant="ghost" onClick={newTopic}>
              + 新话题
            </ActionButton>
          )}
          title="炸鸡队长"
          variant="simulator-home"
        >
          <RouteRegion className={styles['transcriptRegion'] ?? ''} data-region="captain_transcript">
            <ChickenbroTranscript
              messages={messages}
              state={inputState}
              onRetry={retry}
              temporaryAssistantText={streamState.temporaryText}
              scrollTop={scrollTop}
              hasUnseen={streamState.hasUnseen}
              onScroll={(detail) => {
                if (detail.clientHeight <= 0) return
                const distance = Math.max(0, detail.scrollHeight - detail.scrollTop - detail.clientHeight)
                const next = chickenbroFollowFromDistance(streamStateRef.current, distance)
                if (next.followLatest !== streamStateRef.current.followLatest || next.hasUnseen !== streamStateRef.current.hasUnseen) {
                  updateStreamState(next)
                }
              }}
              onReturnToLatest={() => {
                updateStreamState(chickenbroResumeLatest(streamStateRef.current))
                queueScrollToLatest()
              }}
            />
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
