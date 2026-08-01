import Taro from '@tarojs/taro'
import { useCallback, useEffect, useRef, useState } from 'react'

import { taroStorage, wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { ChickenbroArchiveList } from '@wow-mini/design-system/components/ChickenbroChatComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { storageKey, type ChickenbroSessionSummary } from '@wow-mini/domain'

import styles from './chickenbro.module.scss'

type ArchiveState = 'loading' | 'ready' | 'empty' | 'error'

const pendingSessionStorageKey = storageKey('chickenbro.pendingSessionId')

export default function ChickenbroPage() {
  const [sessions, setSessions] = useState<readonly ChickenbroSessionSummary[]>([])
  const [archiveState, setArchiveState] = useState<ArchiveState>('loading')
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const sessionsRef = useRef<readonly ChickenbroSessionSummary[]>([])

  const load = useCallback(async (cursor = '', append = false) => {
    setArchiveState('loading')
    try {
      const result = await wowApi.simulator.chickenbroSessions({
        limit: 20,
        ...(cursor ? { cursor } : {}),
      })
      if (result.fromFallback) {
        setArchiveState('error')
        return
      }
      const next = append
        ? [...sessionsRef.current, ...result.payload.sessions.filter((item) => !sessionsRef.current.some((current) => current.sessionId === item.sessionId))]
        : result.payload.sessions
      sessionsRef.current = next
      setSessions(next)
      setNextCursor(result.payload.nextCursor)
      setArchiveState(next.length === 0 ? 'empty' : 'ready')
    } catch {
      setArchiveState('error')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const selectSession = (session: ChickenbroSessionSummary) => {
    taroStorage.set(pendingSessionStorageKey, session.sessionId)
    void Taro.switchTab({ url: '/pages/simulator/simulator' })
  }

  return (
    <AppShell surfaceAssetId="builds-surface-texture.default" surfaceMode="tile" surfaceSlotId="asset_slot.archive-page-frame">
      <RouteStage className={styles['pageFrame'] ?? ''} routeState={archiveState} targetRegionCount={3} width="inset">
        <PageFrame
          backRegion="chickenbro-archive-back"
          region="page_header"
          title="对话存档"
          variant="chickenbro-chat"
          onBack={() => void Taro.switchTab({ url: '/pages/simulator/simulator' })}
        >
          <RouteRegion className={styles['archiveListRegion'] ?? ''} data-region="archive_list">
            {archiveState === 'ready' ? (
              <ChickenbroArchiveList
                hasMore={Boolean(nextCursor)}
                sessions={sessions}
                state="ready"
                onLoadMore={() => { if (nextCursor) void load(nextCursor, true) }}
                onRetry={() => void load()}
                onSelect={selectSession}
              />
            ) : null}
          </RouteRegion>
          <RouteRegion className={styles['archiveTerminalRegion'] ?? ''} data-region="archive_terminal">
            {archiveState !== 'ready' ? (
              <ChickenbroArchiveList
                hasMore={false}
                sessions={[]}
                state={archiveState}
                onLoadMore={() => undefined}
                onRetry={() => void load()}
                onSelect={selectSession}
              />
            ) : null}
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
