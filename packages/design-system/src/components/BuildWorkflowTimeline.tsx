import { Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'

import type { ProductionAssetId } from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { ProductionAssetImage } from './ProductionAsset'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ForgedPanel } from './ReconstructionPrimitives'
import { SystemGlyph } from './SystemGlyph'
import { styleSelectorClass } from './selector-markers'
import styles from './BuildsHomeComponents.module.scss'

export type BuildWorkflowStageId = 'input' | 'validation' | 'tracking'
export type BuildWorkflowNodeState = 'active_blue' | 'pending_gold' | 'inactive_gray'

export interface BuildWorkflowStage {
  id: BuildWorkflowStageId
  title: string
  detail: string
  state: ReadinessState
  stateLabel: string
  disabled?: boolean | undefined
  glyphAssetId?: ProductionAssetId | undefined
  fallbackGlyphAssetId?: ProductionAssetId | undefined
}

export interface BuildWorkflowTimelineProps {
  stages: readonly BuildWorkflowStage[]
  loading?: boolean | undefined
  onSelect?: ((stage: BuildWorkflowStage) => void) | undefined
}

interface WorkflowGlyph {
  assetId: ProductionAssetId
  fallbackAssetId: ProductionAssetId
}

const workflowStageIds = ['input', 'validation', 'tracking'] as const

const workflowGlyphs: Readonly<Record<BuildWorkflowStageId, WorkflowGlyph>> = {
  input: {
    assetId: 'builds-workflow-medallion.input',
    fallbackAssetId: 'utility-glyph-family.document',
  },
  validation: {
    assetId: 'builds-workflow-medallion.validation',
    fallbackAssetId: 'utility-glyph-family.shield',
  },
  tracking: {
    assetId: 'builds-workflow-medallion.tracking',
    fallbackAssetId: 'utility-glyph-family.records',
  },
}

const workflowNodeAssets: Readonly<Record<BuildWorkflowNodeState, ProductionAssetId>> = {
  active_blue: 'builds-workflow-timeline.node-active',
  pending_gold: 'builds-workflow-timeline.node-pending',
  inactive_gray: 'builds-workflow-timeline.node-inactive',
}

const workflowFallbacks: Readonly<Record<BuildWorkflowStageId, BuildWorkflowStage>> = {
  input: {
    id: 'input',
    title: '输入',
    detail: '整理天赋与装备输入',
    state: 'unknown',
    stateLabel: '待校验',
    disabled: true,
  },
  validation: {
    id: 'validation',
    title: '验证',
    detail: '固定输入后进行 SimC 校验',
    state: 'unknown',
    stateLabel: '待开始',
    disabled: true,
  },
  tracking: {
    id: 'tracking',
    title: '追踪',
    detail: '进入任务列表追踪真实结果',
    state: 'unknown',
    stateLabel: '进入后查看',
    disabled: true,
  },
}

const aggregatePriority: readonly ReadinessState[] = [
  'error',
  'blocked',
  'stale',
  'partial',
  'empty',
  'loading',
  'unknown',
  'source_reference',
  'ready',
]

function buildStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function buildClass(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

function normalizeWorkflowStages(stages: readonly BuildWorkflowStage[]): readonly BuildWorkflowStage[] {
  return workflowStageIds.map((id) => stages.find((stage) => stage.id === id) ?? workflowFallbacks[id])
}

function aggregateWorkflowState(stages: readonly BuildWorkflowStage[], loading: boolean): ReadinessState {
  if (loading) return 'loading'
  return aggregatePriority.find((state) => stages.some((stage) => stage.state === state)) ?? 'unknown'
}

function workflowNodeState(stage: BuildWorkflowStage, loading: boolean): BuildWorkflowNodeState {
  if (loading || stage.disabled === true || stage.state === 'blocked' || stage.state === 'error' || stage.state === 'empty') {
    return 'inactive_gray'
  }
  if (stage.id === 'input') return 'active_blue'
  if (stage.id === 'validation') return 'pending_gold'
  return stage.state === 'ready' || stage.state === 'source_reference'
    ? 'active_blue'
    : 'inactive_gray'
}

export function BuildWorkflowTimeline({
  stages,
  loading = false,
  onSelect,
}: BuildWorkflowTimelineProps) {
  const normalizedStages = normalizeWorkflowStages(stages)
  const ownerState = aggregateWorkflowState(normalizedStages, loading)

  return (
    <View
      className={buildClass(buildStyle('buildOwner'), buildStyle('workflowOwner'))}
      data-owner="build-workflow-timeline"
      data-region="workflow_stage_list"
      data-slot="asset_slot.builds-frame-family"
      data-state={ownerState}
    >
      <ForgedPanel
        className={buildClass(buildStyle('buildFrame'), buildStyle('workflowFrame'))}
        contentInset={4}
        frameAssetId="builds-frame.workflow"
        frameLayer="behind-content"
        frameSlotId="asset_slot.builds-frame-family"
        frameWidth={8}
        interactiveInset={6}
        owner="build-workflow-timeline"
        region="workflow_stage_list"
        tone="inset"
      >
        <View
          className={buildStyle('workflowContent')}
          data-frame-content="true"
          data-slot="workflow-stages"
          data-state={ownerState}
        >
          <ProductionAssetImage
            alt="构筑流程轨道"
            assetId="builds-workflow-timeline.rail"
            className={buildStyle('workflowRail')}
            slotId="asset_slot.builds-workflow-timeline"
          />
          {normalizedStages.map((stage) => {
            const effectiveState: ReadinessState = loading ? 'loading' : stage.state
            const disabled = loading || stage.disabled === true || !onSelect
            const glyph = workflowGlyphs[stage.id]
            const nodeState = workflowNodeState(stage, loading)
            const stateLabel = loading ? '加载中' : stage.stateLabel
            return (
              <ControlButton
                key={stage.id}
                aria-label={[stage.title, stage.detail, stateLabel].join('，')}
                className={buildClass(
                  buildStyle('workflowRow'),
                  disabled && buildStyle('workflowRowDisabled'),
                )}
                data-disabled={disabled ? 'true' : 'false'}
                data-role="build-workflow-stage"
                data-slot={'workflow-stage.' + stage.id}
                data-stage-id={stage.id}
                data-state={effectiveState}
                disabled={disabled}
                {...(!disabled ? { onClick: () => onSelect?.(stage) } : {})}
              >
                <View
                  className={buildStyle('workflowNodeCell')}
                  data-node-state={nodeState}
                  data-slot="asset_slot.builds-workflow-timeline"
                >
                  <ProductionAssetImage
                    alt={stage.title + '阶段节点'}
                    assetId={workflowNodeAssets[nodeState]}
                    className={buildStyle('workflowNode')}
                    slotId="asset_slot.builds-workflow-timeline"
                  />
                </View>
                <View className={buildStyle('workflowMedallion')} data-slot="asset_slot.builds-workflow-medallions">
                  <ProductionAssetGlyph
                    assetId={stage.glyphAssetId ?? glyph.assetId}
                    className={buildStyle('workflowGlyph')}
                    dataRole={'build-workflow-' + stage.id}
                    fallbackAssetId={stage.fallbackGlyphAssetId ?? glyph.fallbackAssetId}
                    fallbackSlotId="asset_slot.utility-glyph-family"
                    slotId="asset_slot.builds-workflow-medallions"
                  />
                </View>
                <View className={buildStyle('workflowCopy')} data-slot="workflow-copy">
                  <Text className={buildStyle('workflowTitle')}>{stage.title}</Text>
                  <Text className={buildStyle('workflowDetail')}>{stage.detail}</Text>
                </View>
                <Text className={buildStyle('workflowStateLabel')} data-state={effectiveState}>
                  {stateLabel}
                </Text>
                <View className={buildStyle('workflowChevron')} data-slot="asset_slot.builds-chevron">
                  <SystemGlyph
                    assetId="utility-glyph-family.chevron-right"
                    className={buildStyle('chevronGlyph')}
                    dataRole="build-workflow-chevron"
                    slotId="asset_slot.utility-glyph-family"
                  />
                </View>
              </ControlButton>
            )
          })}
        </View>
      </ForgedPanel>
    </View>
  )
}
