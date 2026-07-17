import { Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'

import { SystemGlyph } from './SystemGlyph'
import { styleSelectorClass } from './selector-markers'

import styles from './TaskDetailComponents.module.scss'

export type TaskDetailTone = 'neutral' | 'pending' | 'active' | 'success' | 'danger' | 'blocked' | 'verified'
export type TaskDetailResultState = 'loading' | 'pending' | 'completed' | 'failed' | 'unsupported' | 'blocked'
export type TaskProgressState = 'complete' | 'active' | 'waiting' | 'error'

export interface TaskDetailCell {
  id: string
  label: string
  value: string
  detail: string
  tone: TaskDetailTone
}

export interface TaskDetailProgressStep {
  id: string
  label: string
  state: TaskProgressState
}

function panelHeading(title: string, assetId: 'utility-glyph-family.records' | 'utility-glyph-family.runtime' | 'utility-glyph-family.adjust' | 'utility-glyph-family.shield') {
  return (
    <View className={styles['panelHeading'] ?? ''}>
      <SystemGlyph assetId={assetId} slotId="asset_slot.task-detail-section" />
      <Text data-role="task-detail-panel-heading-label">{title}</Text>
    </View>
  )
}

const metadataGlyphs = [
  'utility-glyph-family.document',
  'utility-glyph-family.timer',
  'utility-glyph-family.target',
  'utility-glyph-family.source-link',
] as const

export interface TaskDetailSummaryProps {
  title: string
  description: string
  status: string
  statusLabel: string
  metadata: readonly TaskDetailCell[]
}

export function TaskDetailSummary({ title, description, status, statusLabel, metadata }: TaskDetailSummaryProps) {
  return (
    <View className={`${styles['summary'] ?? ''} ${styles[`summary-${status}`] ?? ''} ${styleSelectorClass('taskDetailSummary')}`} data-owner="task-detail-summary" data-region="task_summary" data-state={status}>
      <View className={styles['summaryEmblem'] ?? ''} data-role="task-detail-summary-emblem">
        <SystemGlyph assetId="utility-glyph-family.document" dataRole="task-detail-summary-identity-glyph" slotId="asset_slot.task-detail-identity" />
      </View>
      <View className={styles['summaryMain'] ?? ''}>
        <View className={styles['summaryCopy'] ?? ''}>
          <Text className={styles['summaryTitle'] ?? ''} data-role="task-detail-summary-title">{title}</Text>
          <Text className={styles['summaryDescription'] ?? ''} data-role="task-detail-summary-description">{description}</Text>
        </View>
        <View className={`${styles['summaryStatus'] ?? ''} ${styles[`tone-${status}`] ?? ''}`} data-role="task-detail-summary-status" data-tone={status}>
          <View className={styles['statusDot'] ?? ''} />
          <Text>{statusLabel}</Text>
        </View>
      </View>
      <View className={styles['summaryMetadata'] ?? ''} data-count={metadata.length}>
        {metadata.map((item, index) => (
          <View key={item.id} className={styles[`tone-${item.tone}`] ?? ''} data-detail-cell-id={item.id} data-role="task-detail-summary-cell" data-tone={item.tone}>
            <SystemGlyph assetId={metadataGlyphs[index] ?? 'utility-glyph-family.document'} slotId="asset_slot.task-detail-metadata" />
            <View><Text data-role="task-detail-cell-label">{item.label}</Text><Text data-role="task-detail-cell-value">{item.value}</Text></View>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface TaskRefreshNoticeProps {
  refreshing: boolean
  blocked: boolean
  onRefresh: () => void
}

export function TaskRefreshNotice({ refreshing, blocked, onRefresh }: TaskRefreshNoticeProps) {
  return (
    <View className={`${styles['refreshNotice'] ?? ''} ${styleSelectorClass('taskRefreshNotice')}`} data-owner="task-refresh-notice" data-region="refresh_notice" data-state={blocked ? 'blocked' : refreshing ? 'refreshing' : 'ready'}>
      <View className={styles['refreshGlyph'] ?? ''} data-role="task-detail-refresh-glyph">
        <SystemGlyph assetId={blocked ? 'utility-glyph-family.warning' : 'source-badge-family.information'} slotId="asset_slot.task-detail-refresh" />
      </View>
      <View>
        <Text data-role="task-detail-refresh-title">{refreshing ? '正在同步当前任务状态' : blocked ? '当前任务详情不可读取' : '结果生成后可在此刷新状态'}</Text>
        <Text data-role="task-detail-refresh-detail">{refreshing ? '保留已返回内容，等待同一任务响应' : '仅请求当前 owner 的同一任务 ID'}</Text>
      </View>
      <ControlButton className={`${refreshing ? styles['refreshDisabled'] ?? '' : ''} ${styleSelectorClass('taskRefreshAction')}`} data-action-id="refresh-task" data-disabled={refreshing ? 'true' : 'false'} disabled={refreshing} onClick={onRefresh}>
        <SystemGlyph assetId="utility-glyph-family.reset" slotId="asset_slot.task-detail-refresh" />
        <Text>{refreshing ? '同步中' : '刷新状态'}</Text>
      </ControlButton>
    </View>
  )
}

export interface TaskSimcResultProps {
  state: TaskDetailResultState
  statusLabel: string
  metricLabel: string
  metricValue: string
  description: string
  progress: readonly TaskDetailProgressStep[]
}

function resultGlyph(state: TaskDetailResultState) {
  if (state === 'completed') return 'utility-glyph-family.target' as const
  if (state === 'failed' || state === 'blocked') return 'utility-glyph-family.warning' as const
  return 'utility-glyph-family.timer' as const
}

export function TaskSimcResult({ state, statusLabel, metricLabel, metricValue, description, progress }: TaskSimcResultProps) {
  return (
    <View className={`${styles['result'] ?? ''} ${styles[`result-${state}`] ?? ''} ${styleSelectorClass('taskSimcResult')}`} data-owner="task-simc-result" data-region="simc_result" data-state={state}>
      <View className={styles['resultHeading'] ?? ''}>
        {panelHeading('SimC 结果', 'utility-glyph-family.runtime')}
        <View className={styles['resultStatus'] ?? ''}>
          <SystemGlyph assetId={resultGlyph(state)} slotId="asset_slot.task-detail-result-status" />
          <Text>{statusLabel}</Text>
        </View>
      </View>
      <View className={styles['resultBody'] ?? ''}>
        <View className={styles['resultFocus'] ?? ''} data-role="task-detail-result-focus">
          <View className={`${styles['resultCore'] ?? ''} ${styles[`resultCore-${state}`] ?? ''}`} data-role="task-detail-result-core" data-state={state}>
            <View className={styles['resultCoreRing'] ?? ''} />
            <SystemGlyph assetId={resultGlyph(state)} slotId="asset_slot.task-detail-result-core" />
          </View>
          <View className={styles['resultCopy'] ?? ''}>
            <Text data-role="task-detail-result-metric-label">{metricLabel}</Text>
            <Text data-role="result-value">{metricValue}</Text>
            <Text data-role="task-detail-result-description">{description}</Text>
          </View>
        </View>
      </View>
      <View className={styles['resultProgress'] ?? ''} data-count={progress.length}>
        {progress.map((step, index) => (
          <View key={step.id} className={styles[`progress-${step.state}`] ?? ''} data-progress-id={step.id} data-state={step.state}>
            <View className={styles['progressMarker'] ?? ''} data-role="task-detail-progress-marker">
              <Text>{index + 1}</Text>
            </View>
            <Text data-role="task-detail-progress-label">{step.label}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}

const contextGlyphs = [
  'utility-glyph-family.target',
  'utility-glyph-family.timer',
  'utility-glyph-family.shield',
  'utility-glyph-family.source-link',
] as const

export interface TaskRunContextProps { items: readonly TaskDetailCell[] }

export function TaskRunContext({ items }: TaskRunContextProps) {
  return (
    <View className={`${styles['compactPanel'] ?? ''} ${styleSelectorClass('taskRunContext')}`} data-owner="task-run-context" data-region="run_context">
      {panelHeading('运行上下文', 'utility-glyph-family.records')}
      <View className={styles['contextGrid'] ?? ''} data-role="task-detail-cell-grid" data-count={items.length}>
        {items.map((item, index) => (
          <View key={item.id} className={styles[`tone-${item.tone}`] ?? ''} data-detail-cell-id={item.id} data-tone={item.tone}>
            <SystemGlyph assetId={contextGlyphs[index] ?? 'utility-glyph-family.document'} slotId="asset_slot.task-detail-context" />
            <View><Text data-role="task-detail-cell-label">{item.label}</Text><Text data-role="task-detail-cell-value">{item.value}</Text></View>
          </View>
        ))}
      </View>
    </View>
  )
}

const scenarioGlyphs = [
  'utility-glyph-family.target',
  'utility-glyph-family.dungeon',
  'utility-glyph-family.group',
  'utility-glyph-family.timer',
] as const

export interface TaskScenarioGridProps { items: readonly TaskDetailCell[] }

export function TaskScenarioGrid({ items }: TaskScenarioGridProps) {
  return (
    <View className={`${styles['scenarioPanel'] ?? ''} ${styleSelectorClass('taskScenarioGrid')}`} data-owner="task-scenario-grid" data-region="scenario">
      {panelHeading('场景', 'utility-glyph-family.adjust')}
      <View className={styles['fourCellGrid'] ?? ''} data-role="task-detail-cell-grid" data-count={items.length}>
        {items.map((item, index) => (
          <View key={item.id} className={styles[`tone-${item.tone}`] ?? ''} data-detail-cell-id={item.id} data-tone={item.tone}>
            <SystemGlyph assetId={scenarioGlyphs[index] ?? 'utility-glyph-family.adjust'} slotId="asset_slot.task-detail-scenario" />
            <View><Text data-role="task-detail-cell-label">{item.label}</Text><Text data-role="task-detail-cell-value">{item.value}</Text></View>
          </View>
        ))}
      </View>
    </View>
  )
}

const attributeGlyphs = [
  'utility-glyph-family.adjust',
  'utility-glyph-family.swords',
  'utility-glyph-family.document',
  'utility-glyph-family.shield',
  'utility-glyph-family.timer',
  'utility-glyph-family.source-link',
] as const

export interface TaskAttributeSnapshotProps {
  items: readonly TaskDetailCell[]
  verified: boolean
  notice: string
  onDetail: () => void
}

export function TaskAttributeSnapshot({ items, verified, notice, onDetail }: TaskAttributeSnapshotProps) {
  return (
    <View className={`${styles['dataPanel'] ?? ''} ${styleSelectorClass('taskAttributeSnapshot')}`} data-owner="task-attribute-snapshot" data-region="attribute_snapshot" data-state={verified ? 'verified' : 'unavailable'}>
      {panelHeading('属性快照', 'utility-glyph-family.adjust')}
      <View className={styles['sixCellGrid'] ?? ''} data-role="task-detail-cell-grid" data-count={items.length}>
        {items.map((item, index) => (
          <View key={item.id} className={styles[`tone-${item.tone}`] ?? ''} data-detail-cell-id={item.id} data-tone={item.tone}>
            <SystemGlyph assetId={attributeGlyphs[index] ?? 'utility-glyph-family.adjust'} slotId="asset_slot.task-detail-attributes" />
            <View><Text data-role="task-detail-cell-label">{item.label}</Text><Text data-role="task-detail-cell-value">{item.value}</Text></View>
          </View>
        ))}
      </View>
      <View className={styles['panelNotice'] ?? ''} data-role="task-detail-panel-notice">
        <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.task-detail-attribute-notice" />
        <Text data-role="task-detail-panel-notice-text">{notice}</Text>
        <ControlButton data-action-id="attribute-detail" onClick={onDetail}>
          <SystemGlyph assetId="utility-glyph-family.records" dataRole="task-detail-panel-action-glyph" slotId="asset_slot.task-detail-attribute-action" />
          <Text>查看详情</Text>
        </ControlButton>
      </View>
    </View>
  )
}

const preparationGlyphs = [
  'utility-glyph-family.flag',
  'utility-glyph-family.flask',
  'utility-glyph-family.utensils',
  'utility-glyph-family.swords',
  'utility-glyph-family.group',
] as const

export interface TaskCombatPreparationProps {
  items: readonly TaskDetailCell[]
  state: 'verified' | 'partial' | 'blocked' | 'unavailable'
  notice: string
  onDetail: () => void
}

export function TaskCombatPreparation({ items, state, notice, onDetail }: TaskCombatPreparationProps) {
  return (
    <View className={`${styles['dataPanel'] ?? ''} ${styleSelectorClass('taskCombatPreparation')}`} data-owner="task-combat-preparation" data-region="combat_buffs" data-state={state}>
      {panelHeading('战斗准备', 'utility-glyph-family.shield')}
      <View className={styles['fiveCellGrid'] ?? ''} data-role="task-detail-cell-grid" data-count={items.length}>
        {items.map((item, index) => (
          <View key={item.id} className={styles[`tone-${item.tone}`] ?? ''} data-detail-cell-id={item.id} data-tone={item.tone}>
            <SystemGlyph assetId={preparationGlyphs[index] ?? 'utility-glyph-family.shield'} slotId="asset_slot.task-detail-preparation" />
            <View><Text data-role="task-detail-cell-label">{item.label}</Text><Text data-role="task-detail-cell-value">{item.value}</Text></View>
          </View>
        ))}
      </View>
      <View className={styles['panelNotice'] ?? ''} data-role="task-detail-panel-notice">
        <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.task-detail-preparation-notice" />
        <Text data-role="task-detail-panel-notice-text">{notice}</Text>
        <ControlButton data-action-id="preparation-detail" onClick={onDetail}>
          <SystemGlyph assetId="utility-glyph-family.records" dataRole="task-detail-panel-action-glyph" slotId="asset_slot.task-detail-preparation-action" />
          <Text>查看详情</Text>
        </ControlButton>
      </View>
    </View>
  )
}

export interface TaskExceptionStateProps {
  state: 'none' | 'failed' | 'blocked'
  title: string
  detail: string
  onDetail: () => void
}

export function TaskExceptionState({ state, title, detail, onDetail }: TaskExceptionStateProps) {
  return (
    <View className={`${styles['exception'] ?? ''} ${styles[`exception-${state}`] ?? ''} ${styleSelectorClass('taskExceptionState')}`} data-owner="task-exception-state" data-region="error_state" data-state={state}>
      <View className={styles['exceptionGlyph'] ?? ''} data-role="task-detail-exception-glyph">
        <SystemGlyph assetId={state === 'none' ? 'utility-glyph-family.shield' : 'utility-glyph-family.warning'} slotId="asset_slot.task-detail-exception" />
      </View>
      <View><Text>{title}</Text><Text data-role="task-detail-exception-detail">{detail}</Text></View>
      <ControlButton data-action-id="exception-detail" data-role="task-detail-exception-action" onClick={onDetail}>
        <Text>查看详情</Text>
        <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.task-detail-exception-action" />
      </ControlButton>
    </View>
  )
}
