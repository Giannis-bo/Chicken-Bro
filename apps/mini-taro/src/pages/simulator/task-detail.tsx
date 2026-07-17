import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import {
  TaskAttributeSnapshot,
  TaskCombatPreparation,
  TaskDetailSummary,
  TaskExceptionState,
  TaskRefreshNotice,
  TaskRunContext,
  TaskScenarioGrid,
  TaskSimcResult,
} from '@wow-mini/design-system/components/TaskDetailComponents'
import type { RouteDataState } from '@wow-mini/domain'

import { goBack, useAsyncRoute } from '../_shared/route-runtime'
import { buildTaskDetailView, type TaskDetailRouteContext } from './task-detail-model'
import styles from './task-detail.module.scss'

function routeContext(
  state: RouteDataState<unknown>,
  hasTask: boolean,
): TaskDetailRouteContext {
  const reason = state.state === 'error'
    ? state.error
    : state.state === 'blocked'
      ? state.reason
      : state.state === 'empty'
        ? '未找到当前 owner 的任务'
        : state.state === 'unknown'
          ? state.reason
          : ''
  if (state.state === 'loading') {
    return { phase: hasTask ? 'ready' : 'loading', reason: '', refreshing: hasTask }
  }
  if (state.state === 'ready' || state.state === 'stale' || state.state === 'partial' || state.state === 'source_reference') {
    return { phase: 'ready', reason: '', refreshing: false }
  }
  return { phase: 'blocked', reason, refreshing: false }
}

function showDetails(title: string, content: string): void {
  void Taro.showModal({
    title,
    content: content.slice(0, 900) || '后端未返回可展示详情',
    showCancel: false,
    confirmText: '知道了',
  })
}

export default function TaskDetailPage() {
  const router = useRouter()
  const id = router.params['id'] ?? ''
  const route = useAsyncRoute(
    () => id
      ? wowApi.simulator.task(id)
      : Promise.resolve({ payload: { task: null }, fromFallback: true, error: '缺少任务 ID' }),
    { fallbackPolicy: 'blocked', isEmpty: (value) => value.task === null },
  )
  const task = route.data?.task ?? undefined
  const context = routeContext(route.state, Boolean(task))
  const view = buildTaskDetailView(task, context)

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.task-detail-page-frame"
    >
      <RouteStage
        className={styles['pageFrame'] ?? ''}
        routeState={route.state.state}
        targetRegionCount={10}
        width="full"
      >
        <PageFrame
          backRegion="task-detail-back"
          region="page_header"
          title="任务详情"
          variant="task-detail"
          onBack={() => goBack('/pages/simulator/tasks')}
        >
          <View className={styles['summaryRegion'] ?? ''}>
            <TaskDetailSummary
              description={view.description}
              metadata={view.metadata}
              status={view.status}
              statusLabel={view.statusLabel}
              title={view.title}
            />
          </View>
          <View className={styles['refreshRegion'] ?? ''}>
            <TaskRefreshNotice
              blocked={view.routePhase === 'blocked'}
              refreshing={view.refreshing}
              onRefresh={route.load}
            />
          </View>
          <View className={styles['resultRegion'] ?? ''}>
            <TaskSimcResult {...view.result} />
          </View>
          <View className={styles['contextRegion'] ?? ''}>
            <TaskRunContext items={view.context} />
          </View>
          <View className={styles['scenarioRegion'] ?? ''}>
            <TaskScenarioGrid items={view.scenario} />
          </View>
          <View className={styles['attributesRegion'] ?? ''}>
            <TaskAttributeSnapshot
              items={view.attributes}
              notice={view.attributeNotice}
              verified={view.attributeVerified}
              onDetail={() => showDetails('属性快照', view.attributeDetail)}
            />
          </View>
          <View className={styles['preparationRegion'] ?? ''}>
            <TaskCombatPreparation
              items={view.preparation}
              notice={view.preparationNotice}
              state={view.preparationState}
              onDetail={() => showDetails('战斗准备', view.preparationDetail)}
            />
          </View>
          <View className={styles['exceptionRegion'] ?? ''}>
            <TaskExceptionState
              {...view.exception}
              onDetail={() => showDetails('任务异常详情', view.exceptionDetail)}
            />
          </View>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
