import { Image, Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'
import { useEffect, useState } from 'react'

import type { ReadinessState } from '@wow-mini/domain'

import { isTrustedRuntimeMediaUrl } from '../runtime-media'
import { ProductionAssetImage } from './ProductionAsset'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ForgedPanel } from './ReconstructionPrimitives'
import { SystemGlyph } from './SystemGlyph'
import { styleSelectorClass } from './selector-markers'
import styles from './BuildsHomeComponents.module.scss'

export interface BuildSpecializationIdentity {
  label?: string | undefined
  name?: string | undefined
  iconUrl?: string | undefined
  sourceUrl?: string | undefined
  sourceReferenced?: boolean | undefined
  verified?: boolean | undefined
  trust?: { level?: string | undefined } | undefined
}

export interface BuildSpecializationOverviewProps {
  title: string
  description: string
  sourceLabel: string
  state: ReadinessState
  stateLabel?: string | undefined
  identity?: BuildSpecializationIdentity | null | undefined
  loading?: boolean | undefined
  onSelect?: (() => void) | undefined
}

const stateLabels: Readonly<Record<ReadinessState, string>> = {
  loading: '加载中',
  empty: '暂无可用专精',
  error: '请求失败',
  blocked: '数据受限',
  partial: '部分可用',
  ready: '可选择',
  stale: '数据过期',
  source_reference: '来源参考',
  unknown: '待校验',
}

function buildStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function buildClass(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

function identityIsSourceReferenced(identity: BuildSpecializationIdentity | null | undefined): boolean {
  return identity?.sourceReferenced === true
    || identity?.verified === true
    || identity?.trust?.level === 'source_referenced'
    || identity?.trust?.level === 'backend_verified'
}

export function BuildSpecializationOverview({
  title,
  description,
  sourceLabel,
  state,
  stateLabel,
  identity,
  loading = false,
  onSelect,
}: BuildSpecializationOverviewProps) {
  const effectiveState: ReadinessState = loading ? 'loading' : state
  const trustedIconUrl = identityIsSourceReferenced(identity)
    && isTrustedRuntimeMediaUrl(identity?.iconUrl)
    ? identity.iconUrl
    : ''
  const [iconFailed, setIconFailed] = useState(false)
  const [iconLoaded, setIconLoaded] = useState(false)

  useEffect(() => {
    setIconFailed(false)
    setIconLoaded(false)
  }, [trustedIconUrl])

  const showSourceIcon = Boolean(trustedIconUrl) && iconLoaded && !iconFailed && !loading
  const interactionDisabled = loading
    || state === 'empty'
    || state === 'error'
    || state === 'blocked'
    || !onSelect
  const identityLabel = identity?.label ?? identity?.name ?? title

  return (
    <View
      className={buildClass(buildStyle('buildOwner'), buildStyle('overviewOwner'))}
      data-owner="build-specialization-overview"
      data-region="specialization_overview"
      data-slot="asset_slot.builds-frame-family"
      data-state={effectiveState}
    >
      <ForgedPanel
        className={buildClass(buildStyle('buildFrame'), buildStyle('overviewFrame'))}
        contentInset={4}
        frameAssetId="builds-frame.overview"
        frameLayer="behind-content"
        frameSlotId="asset_slot.builds-frame-family"
        frameWidth={8}
        interactiveInset={6}
        owner="build-specialization-overview"
        region="specialization_overview"
        tone={effectiveState === 'blocked' || effectiveState === 'error' ? 'blocked' : 'standard'}
      >
        <ControlButton
          aria-label={'选择职业专精，当前为' + identityLabel}
          className={buildStyle('overviewContent')}
          data-disabled={interactionDisabled ? 'true' : 'false'}
          data-frame-content="true"
          data-material-owner="css"
          data-role="build-specialization-selector"
          data-slot="specialization-selector"
          data-state={effectiveState}
          disabled={interactionDisabled}
          {...(!interactionDisabled ? { onClick: onSelect } : {})}
        >
          <View
            className={buildStyle('overviewMedallionPane')}
            data-slot="asset_slot.builds-specialization-medallion"
          >
            <View className={buildStyle('specializationMedallion')}>
              <ProductionAssetImage
                alt="专精徽章外壳"
                assetId="builds-specialization-medallion.shell"
                className={buildStyle('specializationMedallionShell')}
                slotId="asset_slot.builds-specialization-medallion"
              />
              <View className={buildStyle('specializationObjectViewport')}>
                <Image
                  aria-label={identityLabel}
                  className={buildClass(
                    buildStyle('specializationImage'),
                    !showSourceIcon && buildStyle('visuallyHiddenAsset'),
                  )}
                  data-source-trust="source_reference"
                  data-slot="asset_slot.builds-specialization-object"
                  mode="aspectFill"
                  src={trustedIconUrl}
                  onError={() => {
                    setIconFailed(true)
                    setIconLoaded(false)
                  }}
                  onLoad={() => setIconLoaded(true)}
                />
                <View
                  className={buildClass(
                    buildStyle('specializationFallback'),
                    showSourceIcon && buildStyle('visuallyHiddenAsset'),
                  )}
                  data-slot="asset_slot.builds-specialization-medallion"
                >
                  <ProductionAssetGlyph
                    assetId="builds-specialization-medallion.neutral-fallback"
                    className={buildStyle('specializationGlyph')}
                    dataRole="build-specialization-neutral"
                    fallbackAssetId="product-tab-builds-icon.default"
                    fallbackSlotId="asset_slot.product-tab-glyphs"
                    slotId="asset_slot.builds-specialization-medallion"
                  />
                </View>
              </View>
              <View
                className={buildClass(
                  buildStyle('specializationStamp'),
                  !showSourceIcon && buildStyle('specializationStampHidden'),
                )}
                data-slot="asset_slot.builds-specialization-medallion"
              >
                <ProductionAssetGlyph
                  assetId="builds-specialization-medallion.source-reference-stamp"
                  className={buildStyle('specializationStampGlyph')}
                  fallbackAssetId="source-badge-family.reference"
                  fallbackSlotId="asset_slot.source-badge-family"
                  slotId="asset_slot.builds-specialization-medallion"
                />
              </View>
            </View>
          </View>
          <View className={buildStyle('overviewCopy')} data-slot="specialization-copy">
            <View className={buildStyle('overviewTitleRow')}>
              <Text className={buildStyle('overviewTitle')}>{title}</Text>
            </View>
            <View className={buildStyle('overviewStatus')} data-state={effectiveState}>
              <View className={buildStyle('stateDot')} />
              <Text className={buildStyle('overviewStateLabel')}>
                {loading ? stateLabels.loading : stateLabel ?? stateLabels[state]}
              </Text>
            </View>
            <Text className={buildStyle('overviewDescription')}>{description}</Text>
            <View className={buildStyle('overviewSource')} data-slot="asset_slot.source-badge-family">
              <SystemGlyph
                assetId="source-badge-family.reference"
                className={buildStyle('overviewSourceGlyph')}
                slotId="asset_slot.source-badge-family"
              />
              <Text className={buildStyle('overviewSourceLabel')}>{sourceLabel}</Text>
            </View>
          </View>
        </ControlButton>
      </ForgedPanel>
    </View>
  )
}
