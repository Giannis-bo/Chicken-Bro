import { ScrollView, Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'

import { SystemGlyph } from './SystemGlyph'
import { styleSelectorClass } from './selector-markers'

import styles from './TaskListComponents.module.scss'

export type TaskVisualState = 'queued' | 'running' | 'failed' | 'completed' | 'unknown'

export interface TaskOverviewMetric {
  id: Exclude<TaskVisualState, 'unknown'>
  label: string
  count: number
}

export interface TaskOverviewProps {
  metrics: readonly TaskOverviewMetric[]
  recentTitle: string
  recentDetail: string
}

function stateGlyph(state: TaskVisualState): string {
  if (state === 'queued') return 'utility-glyph-family.records'
  if (state === 'running') return 'utility-glyph-family.runtime'
  if (state === 'failed') return 'utility-glyph-family.warning'
  if (state === 'completed') return 'utility-glyph-family.shield'
  return 'utility-glyph-family.topic'
}

export function TaskOverview({ metrics, recentTitle, recentDetail }: TaskOverviewProps) {
  return (
    <View className={`${styles['overview'] ?? ''} ${styleSelectorClass('taskOverview')}`} data-owner="task-overview" data-region="task_summary">
      <View className={styles['overviewIdentity'] ?? ''}>
        <View className={styles['overviewEmblem'] ?? ''} data-role="tasks-overview-emblem">
          <SystemGlyph assetId="utility-glyph-family.shield" slotId="asset_slot.tasks-overview-emblem" />
        </View>
        <View><Text data-role="tasks-overview-title">模拟任务总览</Text><Text>仅统计当前 owner</Text></View>
      </View>
      <View className={styles['overviewMetrics'] ?? ''}>
        {metrics.map((metric) => (
          <View key={metric.id} className={styles[`status-${metric.id}`] ?? ''} data-summary-id={metric.id} data-state={metric.id}>
            <View className={styles['statusDot'] ?? ''} />
            <Text data-role="tasks-overview-label">{metric.label}</Text>
            <Text data-role="tasks-overview-count">{metric.count}</Text>
          </View>
        ))}
      </View>
      <View className={styles['recentRecord'] ?? ''}>
        <View className={styles['recentHeading'] ?? ''}>
          <SystemGlyph assetId="utility-glyph-family.records" slotId="asset_slot.tasks-overview-status" />
          <Text>最近记录</Text>
        </View>
        <Text>{recentTitle}</Text>
        <Text>{recentDetail}</Text>
      </View>
    </View>
  )
}

export interface TaskSyncStateProps {
  state: 'loading' | 'ready' | 'empty' | 'error'
  title: string
  detail: string
  onRetry: () => void
}

export function TaskSyncState({ state, title, detail, onRetry }: TaskSyncStateProps) {
  const hasAction = state === 'error' || state === 'empty'
  return (
    <View className={`${styles['syncState'] ?? ''} ${styles[`sync-${state}`] ?? ''} ${styleSelectorClass('taskSyncState')}`} data-owner="task-sync-state" data-region="loading_state" data-state={state}>
      <View className={`${styles['syncComposition'] ?? ''} ${hasAction ? styles['syncCompositionAction'] ?? '' : ''}`} data-has-action={hasAction ? 'true' : 'false'} data-role="tasks-sync-composition">
        <View className={styles['syncCore'] ?? ''} data-role="tasks-sync-core">
          <View className={styles['syncGlyph'] ?? ''} data-role="tasks-sync-glyph">
            <SystemGlyph
              assetId={state === 'loading' ? 'utility-glyph-family.runtime' : state === 'error' ? 'utility-glyph-family.warning' : 'utility-glyph-family.shield'}
              slotId="asset_slot.tasks-sync"
            />
          </View>
          <View><Text>{title}</Text><Text>{detail}</Text></View>
        </View>
        {hasAction ? (
          <ControlButton data-action-id="retry" onClick={onRetry}>
            <SystemGlyph assetId="utility-glyph-family.reset" slotId="asset_slot.tasks-sync" />
            <Text>{state === 'error' ? '重试' : '刷新'}</Text>
          </ControlButton>
        ) : null}
      </View>
    </View>
  )
}

export type TaskFilterControlId = 'all' | 'queued' | 'running' | 'failed' | 'completed'

export interface TaskFilterControl {
  id: TaskFilterControlId
  label: string
  count: number
}

export interface TaskStatusFiltersProps {
  items: readonly TaskFilterControl[]
  selected: TaskFilterControlId
  sortLabel: string
  onSelect: (id: TaskFilterControlId) => void
  onToggleSort: () => void
}

export function TaskStatusFilters({ items, selected, sortLabel, onSelect, onToggleSort }: TaskStatusFiltersProps) {
  return (
    <View className={`${styles['filters'] ?? ''} ${styleSelectorClass('taskStatusFilters')}`} data-owner="task-status-filters" data-region="task_filters">
      <View className={styles['filterTabs'] ?? ''}>
        {items.map((item) => (
          <ControlButton
            key={item.id}
            className={`${selected === item.id ? styles['filterSelected'] ?? '' : ''} ${styleSelectorClass(`taskFilter${item.id}`)} ${selected === item.id ? styleSelectorClass('taskFilterSelected') : ''}`}
            data-filter-id={item.id}
            data-role="task-status-filter"
            data-selection-material={selected === item.id ? 'active' : 'inactive'}
            data-selected={selected === item.id ? 'true' : 'false'}
            onClick={() => onSelect(item.id)}
          >
            <Text>{item.label}</Text><Text>{item.count}</Text>
          </ControlButton>
        ))}
      </View>
      <ControlButton className={styles['sortControl'] ?? ''} data-action-id="toggle-sort" onClick={onToggleSort}>
        <SystemGlyph assetId="utility-glyph-family.filter" slotId="asset_slot.tasks-filter" />
        <Text>{sortLabel}</Text>
        <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.tasks-filter" />
      </ControlButton>
    </View>
  )
}

export interface TaskRecordListItem {
  id: string
  title: string
  description: string
  tags: readonly string[]
  state: TaskVisualState
  stateLabel: string
  timeLabel: string
  feedback: string
  navigable: boolean
}

export interface TaskRecordListProps {
  items: readonly TaskRecordListItem[]
  loading: boolean
  onSelect: (id: string) => void
}

const visiblePositions = 5

function placeholder(index: number, loading: boolean): TaskRecordListItem {
  return {
    id: '',
    title: loading ? '正在同步任务' : '暂无更多任务',
    description: loading ? '等待后端返回 owner-scoped 任务' : '此位置没有返回任务记录',
    tags: loading ? ['正在读取', '状态待返回', '时间待返回'] : ['构筑未返回', '场景未返回', '任务未返回'],
    state: 'unknown',
    stateLabel: loading ? '加载中' : '不可用',
    timeLabel: '未返回时间',
    feedback: '',
    navigable: false,
  }
}

export function TaskRecordList({ items, loading, onSelect }: TaskRecordListProps) {
  const rows = loading
    ? Array.from({ length: visiblePositions }, (_, index) => placeholder(index, true))
    : [...items, ...Array.from({ length: Math.max(0, visiblePositions - items.length) }, (_, index) => placeholder(index, false))]
  return (
    <View className={`${styles['recordList'] ?? ''} ${styleSelectorClass('taskRecordList')}`} data-owner="task-record-list" data-region="task_list" data-loading={loading ? 'true' : 'false'}>
      <ScrollView className={styles['recordScroll'] ?? ''} scrollY enhanced showScrollbar={false} data-role="task-scroll">
        <View className={styles['recordRows'] ?? ''} data-role="task-record-rows">
          {rows.map((item, index) => (
            <ControlButton
              key={item.id || `placeholder-${index}`}
              className={`${styles['recordRow'] ?? ''} ${styles[`record-${item.state}`] ?? ''} ${!item.navigable ? styles['recordDisabled'] ?? '' : ''}`}
              data-empty={item.id ? 'false' : 'true'}
              data-owner="task-record-row"
              data-state={item.state}
              data-disabled={item.navigable ? 'false' : 'true'}
              {...(item.id ? { 'data-task-id': item.id } : { 'data-placeholder-index': String(index) })}
              disabled={!item.navigable}
              onClick={() => item.id && onSelect(item.id)}
            >
              <View className={styles['recordIdentity'] ?? ''} data-role="tasks-row-identity">
                <SystemGlyph assetId={stateGlyph(item.state)} slotId="asset_slot.tasks-row-identity" />
              </View>
              <View className={styles['recordContent'] ?? ''}>
                <Text className={styles['recordTitle'] ?? ''} data-role="tasks-row-title">{item.title}</Text>
                <View className={styles['recordTags'] ?? ''}>
                  {item.tags.slice(0, 3).map((tag, tagIndex) => <Text key={`${tagIndex}-${tag}`} data-role="tasks-row-tag">{tag}</Text>)}
                </View>
                <Text className={styles['recordDescription'] ?? ''} data-role="tasks-row-description">{item.description}</Text>
                {item.feedback ? (
                  <View className={styles['recordFeedback'] ?? ''}>
                    <SystemGlyph assetId={item.state === 'failed' ? 'utility-glyph-family.warning' : 'utility-glyph-family.source-link'} slotId="asset_slot.tasks-row-feedback" />
                    <Text data-role="tasks-row-feedback">{item.feedback}</Text>
                  </View>
                ) : null}
              </View>
              <View className={styles['recordMeta'] ?? ''}>
                <View><View className={styles['statusDot'] ?? ''} /><Text data-role="tasks-row-state">{item.stateLabel}</Text></View>
                <Text data-role="tasks-row-time">{item.timeLabel}</Text>
                {item.navigable ? <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.tasks-row-status" /> : null}
              </View>
            </ControlButton>
          ))}
        </View>
      </ScrollView>
    </View>
  )
}

export interface TaskGuidanceStep {
  id: string
  title: string
  detail: string
}

export interface TaskEmptyGuidanceProps {
  mode: 'account-empty' | 'filter-empty' | 'flow-guidance'
  title: string
  detail: string
  steps: readonly TaskGuidanceStep[]
}

export function TaskEmptyGuidance({ mode, title, detail, steps }: TaskEmptyGuidanceProps) {
  return (
    <View className={`${styles['guidance'] ?? ''} ${styleSelectorClass('taskGuidance')}`} data-owner="task-empty-guidance" data-region="empty_state" data-mode={mode}>
      <View className={styles['guidanceHeading'] ?? ''} data-role="tasks-guidance-heading">
        <View className={styles['guidanceEmblem'] ?? ''} data-role="tasks-guidance-emblem">
          <SystemGlyph assetId="utility-glyph-family.records" slotId="asset_slot.tasks-empty" />
        </View>
        <View data-role="tasks-guidance-copy"><Text>{title}</Text><Text>{detail}</Text></View>
      </View>
      <View className={styles['guidanceSteps'] ?? ''}>
        <View className={styles['guidanceRail'] ?? ''} data-role="tasks-guidance-rail" />
        {steps.map((step, index) => (
          <View key={step.id} className={styles['guidanceStep'] ?? ''} data-guidance-id={step.id}>
            <Text>{index + 1}</Text>
            <View><Text>{step.title}</Text><Text>{step.detail}</Text></View>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface TaskBottomActionsProps {
  onCreateSimc: () => void
  onOpenWorkbench: () => void
}

export function TaskBottomActions({ onCreateSimc, onOpenWorkbench }: TaskBottomActionsProps) {
  return (
    <View className={`${styles['bottomActions'] ?? ''} ${styleSelectorClass('taskBottomActions')}`} data-owner="task-bottom-actions" data-region="bottom_actions">
      <ControlButton className={styles['bottomActionCool'] ?? ''} data-action-id="create-simc" data-variant="cool" onClick={onCreateSimc}>
        <SystemGlyph assetId="utility-glyph-family.runtime" slotId="asset_slot.tasks-actions" />
        <Text>去 SimC</Text>
      </ControlButton>
      <ControlButton data-action-id="open-workbench" data-variant="warm" onClick={onOpenWorkbench}>
        <SystemGlyph assetId="utility-glyph-family.briefcase" slotId="asset_slot.tasks-actions" />
        <Text>工作台</Text>
      </ControlButton>
    </View>
  )
}
