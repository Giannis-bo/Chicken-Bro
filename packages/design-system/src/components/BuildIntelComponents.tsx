import { Image, Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'

import type { ReadinessState } from '@wow-mini/domain'

import { resolveRuntimeMediaUrl } from '../runtime-media'
import { useTrustedMediaLoadState } from './useTrustedMediaLoadState'
import { ProductionAssetImage } from './ProductionAsset'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ForgedPanel } from './ReconstructionPrimitives'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'
import styles from './BuildIntelComponents.module.scss'

function componentStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function componentClass(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

function stateStyle(state: ReadinessState): string {
  return componentStyle(`state-${state}`)
}

export interface BuildIntelSummaryProps {
  title: string
  description: string
  recordCountLabel: string
  state: ReadinessState
  stateLabel: string
  loading?: boolean
}

export function BuildIntelSummary({
  title,
  description,
  recordCountLabel,
  state,
  stateLabel,
  loading = false,
}: BuildIntelSummaryProps) {
  return (
    <ForgedPanel
      className={componentStyle('summaryOwner')}
      contentInset={7}
      frameAssetId="build-intel-frame.summary"
      frameSlotId="asset_slot.build-intel-frame-family"
      frameWidth={0}
      owner="build-intel-summary"
      region="summary_card"
      tone="raised"
    >
      <View className={componentStyle('summaryContent')} data-frame-content="true">
        <View className={componentStyle('summaryMedallion')} data-role="build-intel-summary-medallion" data-slot-id="asset_slot.build-intel-summary-medallion">
          <ProductionAssetImage
            alt="构筑情报摘要徽章"
            assetId="build-intel-summary-medallion.default"
            className={componentStyle('summaryMedallionAsset')}
            slotId="asset_slot.build-intel-summary-medallion"
          />
        </View>
        <View className={componentStyle('summaryCopy')}>
          {loading ? (
            <>
              <View className={componentStyle('summaryTitleSkeleton')} />
              <View className={componentStyle('summaryCopySkeleton')} />
              <View className={componentStyle('summaryCopySkeletonShort')} />
            </>
          ) : (
            <>
              <Text className={componentStyle('summaryTitle')} data-role="build-intel-summary-title">{title}</Text>
              <Text className={componentStyle('summaryDescription')} data-role="build-intel-summary-description">{description}</Text>
            </>
          )}
        </View>
        <View className={componentStyle('summaryMetrics')}>
          <View className={componentStyle('summaryMetric')}>
            <Text className={componentStyle('summaryMetricLabel')}>来源记录</Text>
            <Text className={componentStyle('summaryMetricValue')} data-role="build-intel-record-count">
              {loading ? '-- 条来源记录' : recordCountLabel}
            </Text>
          </View>
          <View className={componentClass(componentStyle('summaryMetric'), componentStyle('summaryMetricDivider'), stateStyle(state))} data-state={state}>
            <Text className={componentStyle('summaryMetricLabel')}>数据状态</Text>
            <View className={componentStyle('summaryStateValue')}>
              <View className={componentStyle('stateDot')} />
              <Text data-role="build-intel-state-label">{loading ? '读取中' : stateLabel}</Text>
            </View>
          </View>
        </View>
      </View>
    </ForgedPanel>
  )
}

export interface BuildIntelFilterBarProps {
  filterLabel: string
  sortLabel: string
  disabled?: boolean
  onFilter: () => void
  onSort: () => void
}

export function BuildIntelFilterBar({
  filterLabel,
  sortLabel,
  disabled = false,
  onFilter,
  onSort,
}: BuildIntelFilterBarProps) {
  return (
    <ForgedPanel
      className={componentStyle('filterOwner')}
      contentInset={3}
      frameAssetId="build-intel-frame.filter"
      frameSlotId="asset_slot.build-intel-frame-family"
      frameWidth={0}
      owner="build-intel-filter-bar"
      region="filter_sort_bar"
      tone="inset"
    >
      <View className={componentStyle('filterContent')} data-frame-content="true">
        <ControlButton
          aria-label={`切换职责筛选，当前${filterLabel}`}
          className={componentStyle('filterButton')}
          data-role="build-intel-filter-control"
          data-disabled={disabled ? 'true' : 'false'}
          disabled={disabled}
          onClick={onFilter}
        >
          <SystemGlyph
            assetId="utility-glyph-family.filter"
            className={componentStyle('filterGlyph')}
            dataRole="build-intel-filter-glyph"
            slotId="asset_slot.build-intel-filter-sort-glyphs"
          />
          <Text data-role="build-intel-filter-label">{filterLabel}</Text>
        </ControlButton>
        <ControlButton
          aria-label={`切换排序，当前${sortLabel}`}
          className={componentClass(
            componentStyle('filterButton'),
            componentStyle('sortButton'),
            componentStyle(sortLabel.includes('来源') ? 'sortSource' : 'sortName'),
          )}
          data-role="build-intel-sort-control"
          data-disabled={disabled ? 'true' : 'false'}
          disabled={disabled}
          onClick={onSort}
        >
          <Text data-role="build-intel-sort-label">{sortLabel}</Text>
          <SystemGlyph
            assetId="utility-glyph-family.chevron-right"
            className={componentStyle('sortGlyph')}
            slotId="asset_slot.build-intel-filter-sort-glyphs"
          />
        </ControlButton>
      </View>
    </ForgedPanel>
  )
}

export interface BuildIntelCardMetadata {
  id: 'source' | 'window' | 'note'
  label: string
  value: string
  state: ReadinessState
}

export interface BuildIntelCardProps {
  id: string
  title: string
  description: string
  iconUrl?: string
  state: ReadinessState
  stateLabel: string
  metadata: readonly BuildIntelCardMetadata[]
  primaryLabel: string
  secondaryLabel: string
  primaryDisabled?: boolean
  secondaryDisabled?: boolean
  loading?: boolean
  onPrimary?: () => void
  onSecondary?: () => void
}

const metadataGlyph: Readonly<Record<BuildIntelCardMetadata['id'], string>> = {
  source: 'utility-glyph-family.source-link',
  window: 'utility-glyph-family.runtime',
  note: 'utility-glyph-family.document',
}

export function BuildIntelCard({
  id,
  title,
  description,
  iconUrl,
  state,
  stateLabel,
  metadata,
  primaryLabel,
  secondaryLabel,
  primaryDisabled = false,
  secondaryDisabled = false,
  loading = false,
  onPrimary,
  onSecondary,
}: BuildIntelCardProps) {
  const trustedIconUrl = resolveRuntimeMediaUrl(iconUrl)
  const iconLoadState = useTrustedMediaLoadState(trustedIconUrl)
  const showTrustedIcon = iconLoadState.visible && !loading

  return (
    <ForgedPanel
      className={componentStyle('cardOwner')}
      contentInset={6}
      frameAssetId="build-intel-frame.card"
      frameSlotId="asset_slot.build-intel-frame-family"
      frameWidth={0}
      owner="build-intel-card"
      region="build_card"
      tone={state === 'blocked' || state === 'error' ? 'blocked' : 'standard'}
    >
      <View className={componentStyle('cardContent')} data-card-id={id} data-frame-content="true" data-state={state}>
        <View className={componentStyle('cardTop')}>
          <View className={componentStyle('cardMedallion')} data-role="build-intel-card-medallion" data-slot-id="asset_slot.build-intel-card-medallion-shell">
            <ProductionAssetImage
              alt="专精情报徽章外壳"
              assetId="build-intel-card-medallion-shell.default"
              className={componentStyle('cardMedallionShell')}
              slotId="asset_slot.build-intel-card-medallion-shell"
            />
            {trustedIconUrl ? (
              <Image
                aria-label={title}
                className={componentClass(componentStyle('cardIcon'), !showTrustedIcon && componentStyle('hiddenMedia'))}
                data-source-trust="source_reference"
                data-slot-id="asset_slot.build-intel-specialization-object"
                mode="aspectFill"
                src={trustedIconUrl}
                onError={iconLoadState.onError}
                onLoad={iconLoadState.onLoad}
              />
            ) : null}
            <View className={componentClass(componentStyle('cardIconFallback'), showTrustedIcon && componentStyle('hiddenMedia'))}>
              <SystemGlyph assetId="utility-glyph-family.shield" slotId="asset_slot.utility-glyph-family" />
            </View>
          </View>
          <View className={componentStyle('cardCopy')}>
            {loading ? (
              <>
                <View className={componentStyle('cardTitleSkeleton')} />
                <View className={componentStyle('cardStatusSkeleton')} />
                <View className={componentStyle('cardCopySkeleton')} />
                <View className={componentStyle('cardCopySkeletonShort')} />
              </>
            ) : (
              <>
                <Text className={componentStyle('cardTitle')} data-role="build-intel-card-title">{title}</Text>
                <View className={componentClass(componentStyle('cardStatus'), stateStyle(state))} data-state={state}>
                  <View className={componentStyle('stateDot')} />
                  <Text>{stateLabel}</Text>
                </View>
                <Text className={componentStyle('cardDescription')} data-role="build-intel-card-description">{description}</Text>
              </>
            )}
          </View>
          <View
            className={componentClass(componentStyle('cardActions'), 'wx-data-control-cell')}
            data-control-roles="build-intel-primary-action,build-intel-secondary-action"
          >
            <ControlButton
              aria-label={primaryLabel}
              className={componentClass(
                componentStyle('primaryAction'),
                (primaryDisabled || loading) && componentStyle('primaryActionDisabled'),
              )}
              data-disabled={primaryDisabled || loading ? 'true' : 'false'}
              data-material-owner="asset"
              data-role="build-intel-primary-action"
              data-slot-id="asset_slot.build-intel-primary-action"
              disabled={primaryDisabled || loading}
              {...(!primaryDisabled && !loading && onPrimary ? { onClick: onPrimary } : {})}
            >
              <ProductionAssetImage
                alt="查看天赋动作底板"
                assetId="build-intel-primary-action.default"
                className={componentStyle('primaryActionAsset')}
                fit="cover"
                slotId="asset_slot.build-intel-primary-action"
              />
              <ProductionAssetGlyph
                assetId="quick-action-talents-glyph.default"
                className={componentStyle('primaryActionGlyph')}
                fallbackAssetId="utility-glyph-family.topic"
                fallbackSlotId="asset_slot.utility-glyph-family"
                slotId="asset_slot.build-intel-primary-action"
              />
              <Text data-role="build-intel-primary-action-label">{primaryLabel}</Text>
            </ControlButton>
            <ControlButton
              aria-label={secondaryLabel}
              className={componentClass(
                componentStyle('secondaryAction'),
                (secondaryDisabled || loading) && componentStyle('secondaryActionDisabled'),
              )}
              data-disabled={secondaryDisabled || loading ? 'true' : 'false'}
              data-role="build-intel-secondary-action"
              disabled={secondaryDisabled || loading}
              {...(!secondaryDisabled && !loading && onSecondary ? { onClick: onSecondary } : {})}
            >
              <Text data-role="build-intel-secondary-action-label">{secondaryLabel}</Text>
              <SystemGlyph
                assetId="utility-glyph-family.chevron-right"
                className={componentStyle('secondaryActionGlyph')}
                slotId="asset_slot.utility-glyph-family"
              />
            </ControlButton>
          </View>
        </View>
        <View className={componentStyle('cardMetadata')} data-metadata-count={metadata.length}>
          {metadata.map((entry, index) => (
            <View
              key={entry.id}
              className={componentClass(
                componentStyle('metadataItem'),
                index > 0 && componentStyle('metadataItemDivider'),
                stateStyle(entry.state),
              )}
              data-metadata-id={entry.id}
              data-state={entry.state}
            >
              <SystemGlyph assetId={metadataGlyph[entry.id]} slotId="asset_slot.build-intel-metadata-glyphs" />
              <View className={componentStyle('metadataCopy')}>
                <Text className={componentStyle('metadataLabel')}>{entry.label}</Text>
                <Text className={componentStyle('metadataValue')} data-role={`build-intel-metadata-${entry.id}`}>{loading ? '读取中' : entry.value}</Text>
              </View>
            </View>
          ))}
        </View>
      </View>
    </ForgedPanel>
  )
}

export interface BuildIntelDisclaimerProps {
  copy: string
}

export function BuildIntelDisclaimer({ copy }: BuildIntelDisclaimerProps) {
  return (
    <ForgedPanel
      className={componentStyle('disclaimerOwner')}
      contentInset={4}
      frameAssetId="build-intel-frame.disclaimer"
      frameSlotId="asset_slot.build-intel-frame-family"
      frameWidth={0}
      owner="build-intel-disclaimer"
      region="reference_disclaimer"
      tone="inset"
    >
      <View className={componentStyle('disclaimerContent')} data-frame-content="true">
        <SystemGlyph assetId="source-badge-family.information" dataRole="build-intel-disclaimer-glyph" slotId="asset_slot.build-intel-disclaimer-glyph" />
        <Text data-role="build-intel-disclaimer-copy">{copy}</Text>
      </View>
    </ForgedPanel>
  )
}
