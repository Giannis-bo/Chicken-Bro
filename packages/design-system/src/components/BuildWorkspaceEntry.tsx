import { Text, View } from '@tarojs/components'

import { assetRuntimePath } from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { NineSliceFrame } from './NineSliceFrame'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ForgedPanel } from './ReconstructionPrimitives'
import { styleSelectorClass } from './selector-markers'
import styles from './BuildsHomeComponents.module.scss'

export interface BuildWorkspaceEntryProps {
  title: string
  statusLabel: string
  summary: string
  detail: string
  state: ReadinessState
  actionLabel?: string | undefined
  disabled?: boolean | undefined
  loading?: boolean | undefined
  onEnter?: (() => void) | undefined
}

function buildStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function buildClass(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

export function BuildWorkspaceEntry({
  title,
  statusLabel,
  summary,
  detail,
  state,
  actionLabel = '进入工作台',
  disabled = false,
  loading = false,
  onEnter,
}: BuildWorkspaceEntryProps) {
  const effectiveState: ReadinessState = loading ? 'loading' : state
  const actionDisabled = disabled
    || loading
    || !onEnter
  const medallionAssetId = effectiveState === 'blocked' || effectiveState === 'error' || effectiveState === 'empty'
    ? 'builds-workspace-medallion.blocked'
    : 'builds-workspace-medallion.default'
  const medallionAssetReady = Boolean(assetRuntimePath(medallionAssetId))
  const actionFrameReady = Boolean(assetRuntimePath('builds-frame.primary-action'))

  return (
    <View
      className={buildClass(buildStyle('buildOwner'), buildStyle('workspaceOwner'))}
      data-owner="build-workspace-entry"
      data-region="active_specialization_workspace"
      data-slot="asset_slot.builds-frame-family"
      data-state={effectiveState}
    >
      <ForgedPanel
        className={buildClass(buildStyle('buildFrame'), buildStyle('workspaceFrame'))}
        contentInset={5}
        frameAssetId="builds-frame.workspace-gold"
        frameLayer="behind-content"
        frameSlotId="asset_slot.builds-frame-family"
        frameWidth={9}
        interactiveInset={7}
        owner="build-workspace-entry"
        region="active_specialization_workspace"
        tone={effectiveState === 'blocked' || effectiveState === 'error' ? 'blocked' : 'bright'}
      >
        <View
          className={buildStyle('workspaceContent')}
          data-frame-content="true"
          data-slot="workspace-entry"
          data-state={effectiveState}
        >
          <View className={buildStyle('workspaceMedallionPane')} data-slot="asset_slot.builds-workspace-medallion">
            <View className={buildClass(
              buildStyle('workspaceMedallion'),
              medallionAssetReady && buildStyle('workspaceMedallionMaterial'),
            )}>
              <ProductionAssetGlyph
                assetId={medallionAssetId}
                className={buildClass(
                  buildStyle('workspaceGlyph'),
                  medallionAssetReady && buildStyle('workspaceGlyphMaterial'),
                )}
                dataRole="build-workspace-medallion"
                fallbackAssetId="utility-glyph-family.adjust"
                fallbackSlotId="asset_slot.utility-glyph-family"
                slotId="asset_slot.builds-workspace-medallion"
              />
            </View>
          </View>
          <View className={buildStyle('workspaceCopy')} data-slot="workspace-copy">
            <View className={buildStyle('workspaceHeading')}>
              <Text className={buildStyle('workspaceTitle')}>{title}</Text>
              <View className={buildStyle('workspaceStatus')} data-state={effectiveState}>
                <View className={buildStyle('stateDot')} />
                <Text className={buildStyle('workspaceStateLabel')}>
                  {loading ? '加载中' : statusLabel}
                </Text>
              </View>
            </View>
            <Text className={buildStyle('workspaceSummary')}>{summary}</Text>
            <Text className={buildStyle('workspaceDetail')}>{detail}</Text>
          </View>
          <View
            className={buildStyle('workspaceAction')}
            data-disabled={actionDisabled ? 'true' : 'false'}
            data-slot="asset_slot.builds-frame-family"
          >
            <View
              aria-label={actionLabel}
              className={buildClass(
                buildStyle('workspaceActionButton'),
                actionFrameReady && buildStyle('workspaceActionButtonMaterial'),
                actionDisabled && buildStyle('workspaceActionButtonDisabled'),
              )}
              data-frame-asset-ready={actionFrameReady ? 'true' : 'false'}
              data-disabled={actionDisabled ? 'true' : 'false'}
              data-slot="workspace-action"
              role="button"
              {...(!actionDisabled ? { onClick: onEnter } : {})}
            >
              {actionFrameReady ? (
                <NineSliceFrame
                  assetId="builds-frame.primary-action"
                  className={buildStyle('workspaceActionFrame')}
                  frameWidth={6}
                  scope="control"
                  slotId="asset_slot.builds-frame-family"
                />
              ) : null}
              <View
                className={buildStyle('workspaceActionContent')}
                data-slot="asset_slot.builds-primary-action-glyph"
              >
                <ProductionAssetGlyph
                  assetId="builds-primary-action-glyph.default"
                  className={buildStyle('workspaceActionGlyph')}
                  dataRole="build-workspace-action"
                  fallbackAssetId="product-tab-builds-icon.default"
                  fallbackSlotId="asset_slot.product-tab-glyphs"
                  slotId="asset_slot.builds-primary-action-glyph"
                />
                <Text className={buildStyle('workspaceActionLabel')}>{actionLabel}</Text>
              </View>
            </View>
          </View>
        </View>
      </ForgedPanel>
    </View>
  )
}
