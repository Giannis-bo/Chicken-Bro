import { useDidShow } from '@tarojs/taro'
import { useMemo, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import {
  TaskBottomActions,
  TaskEmptyGuidance,
  TaskOverview,
  TaskRecordList,
  TaskStatusFilters,
  TaskSyncState,
  type TaskFilterControl,
} from '@wow-mini/design-system/components/TaskListComponents'

import { goBack, navigateTo, useAsyncRoute } from '../_shared/route-runtime'
import {
  filterAndSortTasks,
  latestTaskSummary,
  taskRecordView,
  taskSummaryMetrics,
  type TaskFilterId,
  type TaskSortOrder,
} from './tasks-list-model'
import styles from './tasks.module.scss'

const guidanceSteps = [
  { id: 'submit', title: '前往 SimC', detail: '配置并提交任务' },
  { id: 'track', title: '任务在此追踪', detail: '查看状态与进度' },
  { id: 'review', title: '完成后查看记录', detail: '进入真实任务详情' },
] as const

export default function TasksPage() {
  const resumed = useRef(false)
  const [filter, setFilter] = useState<TaskFilterId>('all')
  const [sortOrder, setSortOrder] = useState<TaskSortOrder>('newest')
  const route = useAsyncRoute(
    () => wowApi.simulator.tasks(),
    { fallbackPolicy: 'blocked', isEmpty: (value) => value.tasks.length === 0 },
  )
  useDidShow(() => {
    if (!resumed.current) {
      resumed.current = true
      return
    }
    void route.load()
  })

  const tasks = route.data?.tasks ?? []
  const metrics = taskSummaryMetrics(tasks)
  const recent = latestTaskSummary(tasks)
  const visibleTasks = useMemo(
    () => filterAndSortTasks(tasks, filter, sortOrder).map(taskRecordView),
    [filter, sortOrder, tasks],
  )
  const filterItems: readonly TaskFilterControl[] = [
    { id: 'all', label: '全部', count: tasks.length },
    ...metrics.map((metric) => ({ id: metric.id, label: metric.label, count: metric.count })),
  ]
  const initialLoading = route.state.state === 'loading' && tasks.length === 0
  const routeError = route.state.state === 'error' || route.state.state === 'blocked'
  const routeErrorDetail = route.state.state === 'error'
    ? route.state.error
    : route.state.state === 'blocked'
      ? route.state.reason
      : ''
  const ownerEmpty = route.state.state === 'empty'
  const filteredEmpty = tasks.length > 0 && visibleTasks.length === 0
  const syncState = initialLoading ? 'loading' : routeError ? 'error' : ownerEmpty ? 'empty' : 'ready'
  const syncCopy = initialLoading
    ? { title: '正在加载任务中...', detail: '请稍候，正在同步最新状态' }
    : routeError
      ? {
          title: '任务同步失败',
          detail: routeErrorDetail,
        }
      : ownerEmpty
        ? { title: '任务同步完成', detail: '当前 owner 没有返回任务记录' }
        : { title: '任务同步完成', detail: `已返回 ${tasks.length} 条 owner-scoped 任务` }
  const guidanceMode = ownerEmpty
    ? 'account-empty'
    : filteredEmpty
      ? 'filter-empty'
      : 'flow-guidance'
  const guidanceCopy = guidanceMode === 'account-empty'
    ? { title: '暂无任务记录', detail: '当前账户或游客标识没有返回任务' }
    : guidanceMode === 'filter-empty'
      ? { title: '当前筛选暂无任务', detail: '切换“全部”可查看其他真实任务' }
      : { title: '任务使用流程', detail: '应用指引不代表任务已经完成' }

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.tasks-page-frame"
    >
      <RouteStage className={styles['pageFrame'] ?? ''} routeState={route.state.state} targetRegionCount={8} width="full">
        <PageFrame
          backRegion="tasks-list-back"
          region="page_header"
          title="模拟任务台"
          variant="tasks-list"
          onBack={() => goBack('/pages/simulator/simulator')}
        >
          <RouteRegion className={styles['summaryRegion'] ?? ''}>
            <TaskOverview metrics={metrics} recentDetail={recent.detail} recentTitle={recent.title} />
          </RouteRegion>
          <RouteRegion className={styles['syncRegion'] ?? ''}>
            <TaskSyncState state={syncState} title={syncCopy.title} detail={syncCopy.detail} onRetry={route.load} />
          </RouteRegion>
          <RouteRegion className={styles['filtersRegion'] ?? ''}>
            <TaskStatusFilters
              items={filterItems}
              selected={filter}
              sortLabel={sortOrder === 'newest' ? '最新' : '最早'}
              onSelect={setFilter}
              onToggleSort={() => setSortOrder((current) => current === 'newest' ? 'oldest' : 'newest')}
            />
          </RouteRegion>
          <RouteRegion className={styles['listRegion'] ?? ''}>
            <TaskRecordList
              items={visibleTasks}
              loading={initialLoading}
              onSelect={(id) => navigateTo('/pages/simulator/task-detail', { id })}
            />
          </RouteRegion>
          <RouteRegion className={styles['guidanceRegion'] ?? ''}>
            <TaskEmptyGuidance
              detail={guidanceCopy.detail}
              mode={guidanceMode}
              steps={guidanceSteps}
              title={guidanceCopy.title}
            />
          </RouteRegion>
          <RouteRegion className={styles['actionsRegion'] ?? ''}>
            <TaskBottomActions
              onCreateSimc={() => navigateTo('/pages/simulator/simc', { from: 'tasks' })}
              onOpenWorkbench={() => navigateTo('/pages/builds/workbench', { from: 'tasks' })}
            />
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
