import { Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'

import type { ProductionAssetId } from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ForgedPanel } from './ReconstructionPrimitives'
import { SystemGlyph } from './SystemGlyph'
import { styleSelectorClass } from './selector-markers'
import styles from './BuildsHomeComponents.module.scss'

export type BuildEvidenceItemId = 'talents' | 'gear' | 'simc' | 'tasks'
export type BuildEvidenceNavigatorVariant = 'grid' | 'list'

export interface BuildEvidenceItem {
  id: BuildEvidenceItemId
  title: string
  detail: string
  value: string
  state: ReadinessState
  stateLabel: string
  disabled?: boolean | undefined
  glyphAssetId?: ProductionAssetId | undefined
  fallbackGlyphAssetId?: ProductionAssetId | undefined
}

export interface BuildEvidenceNavigatorProps {
  items: readonly BuildEvidenceItem[]
  variant: BuildEvidenceNavigatorVariant
  loading?: boolean | undefined
  onSelect?: ((item: BuildEvidenceItem) => void) | undefined
}

interface EvidenceGlyph {
  assetId: ProductionAssetId
  fallbackAssetId: ProductionAssetId
}

const evidenceItemIds = ['talents', 'gear', 'simc', 'tasks'] as const

const evidenceGlyphs: Readonly<Record<BuildEvidenceItemId, EvidenceGlyph>> = {
  talents: {
    assetId: 'builds-evidence-medallion.talents',
    fallbackAssetId: 'quick-action-talents-glyph.default',
  },
  gear: {
    assetId: 'builds-evidence-medallion.gear',
    fallbackAssetId: 'quick-action-gear-glyph.default',
  },
  simc: {
    assetId: 'builds-evidence-medallion.simc',
    fallbackAssetId: 'quick-action-simc-glyph.default',
  },
  tasks: {
    assetId: 'builds-evidence-medallion.tasks',
    fallbackAssetId: 'utility-glyph-family.records',
  },
}

const evidenceFallbacks: Readonly<Record<BuildEvidenceItemId, BuildEvidenceItem>> = {
  talents: {
    id: 'talents',
    title: '天赋',
    detail: '天赋来源尚未读取',
    value: '数据不可用',
    state: 'unknown',
    stateLabel: '待校验',
    disabled: true,
  },
  gear: {
    id: 'gear',
    title: '装备',
    detail: '装备来源尚未读取',
    value: '数据不可用',
    state: 'unknown',
    stateLabel: '待校验',
    disabled: true,
  },
  simc: {
    id: 'simc',
    title: 'SimC',
    detail: 'SimC 状态尚未读取',
    value: '数据不可用',
    state: 'unknown',
    stateLabel: '待校验',
    disabled: true,
  },
  tasks: {
    id: 'tasks',
    title: '任务',
    detail: '任务状态尚未读取',
    value: '数据不可用',
    state: 'unknown',
    stateLabel: '待校验',
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

function normalizeEvidenceItems(items: readonly BuildEvidenceItem[]): readonly BuildEvidenceItem[] {
  return evidenceItemIds.map((id) => items.find((item) => item.id === id) ?? evidenceFallbacks[id])
}

function aggregateEvidenceState(items: readonly BuildEvidenceItem[], loading: boolean): ReadinessState {
  if (loading) return 'loading'
  return aggregatePriority.find((state) => items.some((item) => item.state === state)) ?? 'unknown'
}

export function BuildEvidenceNavigator({
  items,
  variant,
  loading = false,
  onSelect,
}: BuildEvidenceNavigatorProps) {
  const normalizedItems = normalizeEvidenceItems(items)
  const region = variant === 'grid' ? 'evidence_category_grid' : 'evidence_category_list'
  const ownerState = aggregateEvidenceState(normalizedItems, loading)
  const frameAssetId = variant === 'grid'
    ? 'builds-frame.evidence-grid'
    : 'builds-frame.evidence-list'

  return (
    <View
      className={buildClass(
        buildStyle('buildOwner'),
        buildStyle('evidenceOwner'),
        buildStyle(variant === 'grid' ? 'evidenceOwnerGrid' : 'evidenceOwnerList'),
      )}
      data-owner="build-evidence-navigator"
      data-region={region}
      data-slot="asset_slot.builds-frame-family"
      data-state={ownerState}
      data-variant={variant}
    >
      <ForgedPanel
        className={buildClass(buildStyle('buildFrame'), buildStyle('evidenceFrame'))}
        contentInset={4}
        frameAssetId={frameAssetId}
        frameLayer="behind-content"
        frameSlotId="asset_slot.builds-frame-family"
        frameWidth={8}
        interactiveInset={6}
        owner="build-evidence-navigator"
        region={region}
        tone="inset"
      >
        <View
          className={buildClass(
            buildStyle('evidenceContent'),
            buildStyle(variant === 'grid' ? 'evidenceContentGrid' : 'evidenceContentList'),
          )}
          data-frame-content="true"
          data-slot="evidence-items"
          data-state={ownerState}
          data-variant={variant}
        >
          {normalizedItems.map((item) => {
            const effectiveState: ReadinessState = loading ? 'loading' : item.state
            const disabled = loading || item.disabled === true || !onSelect
            const glyph = evidenceGlyphs[item.id]
            const stateLabel = loading ? '加载中' : item.stateLabel
            const value = loading ? '等待数据' : item.value
            return (
              <ControlButton
                key={item.id}
                aria-label={[item.title, stateLabel, value, item.detail].join('，')}
                className={buildClass(
                  buildStyle('evidenceItem'),
                  disabled && buildStyle('evidenceItemDisabled'),
                )}
                data-detail={item.detail}
                data-disabled={disabled ? 'true' : 'false'}
                data-item-id={item.id}
                data-material-owner="css"
                data-role="build-evidence-item"
                data-slot={'evidence-item.' + item.id}
                data-state={effectiveState}
                disabled={disabled}
                {...(!disabled ? { onClick: () => onSelect?.(item) } : {})}
              >
                <View
                  className={buildStyle('evidenceMedallion')}
                  data-slot="asset_slot.builds-evidence-medallions"
                >
                  <ProductionAssetGlyph
                    assetId={item.glyphAssetId ?? glyph.assetId}
                    className={buildStyle('evidenceGlyph')}
                    dataRole={'build-evidence-' + item.id}
                    fallbackAssetId={item.fallbackGlyphAssetId ?? glyph.fallbackAssetId}
                    fallbackSlotId="asset_slot.utility-glyph-family"
                    slotId="asset_slot.builds-evidence-medallions"
                  />
                </View>
                <View className={buildStyle('evidenceCopy')} data-slot="evidence-copy">
                  <Text className={buildStyle('evidenceTitle')}>{item.title}</Text>
                  <View className={buildStyle('evidenceStatus')} data-state={effectiveState}>
                    <View className={buildStyle('stateDot')} />
                    <Text className={buildStyle('evidenceStateLabel')}>{stateLabel}</Text>
                  </View>
                </View>
                <Text className={buildStyle('evidenceValue')} data-slot="evidence-value">
                  {value}
                </Text>
                <View className={buildStyle('evidenceChevron')} data-slot="asset_slot.builds-chevron">
                  <SystemGlyph
                    assetId="utility-glyph-family.chevron-right"
                    className={buildStyle('chevronGlyph')}
                    dataRole="build-evidence-chevron"
                    slotId="asset_slot.utility-glyph-family"
                  />
                </View>
              </ControlButton>
            )
          })}
          <View
            aria-hidden
            className={buildStyle('evidenceGridCross')}
            data-slot="evidence-grid-dividers"
          >
            <View className={buildStyle('evidenceGridDividerVertical')} />
            <View className={buildStyle('evidenceGridDividerHorizontal')} />
            <View className={buildStyle('evidenceGridDiamond')} />
          </View>
        </View>
      </ForgedPanel>
    </View>
  )
}
