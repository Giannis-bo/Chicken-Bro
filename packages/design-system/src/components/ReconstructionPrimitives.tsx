import { Text, View } from '@tarojs/components'
import type { CSSProperties, ReactNode } from 'react'

import {
  assetRuntimePath,
  type AssetSlotId,
  type ProductionAssetId,
} from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { NineSliceFrame } from './NineSliceFrame'
import { ActionButton } from './ActionButton'
import { ProductionAssetImage } from './ProductionAsset'
import { StatusVisual } from './StatusVisual'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'

export type ForgedPanelTone = 'standard' | 'raised' | 'bright' | 'blocked' | 'inset'
export type ForgedPanelFrameLayer = 'behind-content' | 'overlay'
export type ForgedPanelMaterialFamily = 'default' | 'news'

export interface ForgedPanelProps {
  children: ReactNode
  owner: string
  region: string
  tone?: ForgedPanelTone | undefined
  className?: string | undefined
  frameAssetId?: ProductionAssetId | undefined
  frameSlotId?: AssetSlotId | undefined
  frameWidth?: number | undefined
  frameLayer?: ForgedPanelFrameLayer | undefined
  frameMode?: 'material' | 'none' | undefined
  materialFamily?: ForgedPanelMaterialFamily | undefined
  contentInset?: number | undefined
  interactiveInset?: number | undefined
  onClick?: (() => void) | undefined
}

const toneClass: Readonly<Record<ForgedPanelTone, string>> = {
  standard: '',
  raised: reconstructionStyle('forgedPanelRaised'),
  bright: reconstructionStyle('forgedPanelBright'),
  blocked: reconstructionStyle('forgedPanelBlocked'),
  inset: reconstructionStyle('forgedPanelInset'),
}

const toneAsset: Readonly<Record<ForgedPanelTone, ProductionAssetId>> = {
  standard: 'forged-panel-material-family.standard',
  raised: 'forged-panel-material-family.raised',
  bright: 'forged-panel-material-family.bright',
  blocked: 'forged-panel-material-family.bright',
  inset: 'forged-panel-material-family.compact-card',
}

export function ForgedPanel({
  children,
  owner,
  region,
  tone = 'standard',
  className,
  frameAssetId,
  frameSlotId,
  frameWidth = 14,
  frameLayer = 'behind-content',
  frameMode = 'material',
  materialFamily = 'default',
  contentInset,
  interactiveInset,
  onClick,
}: ForgedPanelProps) {
  const assetId = frameAssetId ?? toneAsset[tone]
  const slotId = frameSlotId ?? 'asset_slot.forged-panel-material-family'
  const frameAssetReady = frameMode === 'material' && Boolean(assetRuntimePath(assetId))
  const safeAreaStyle = contentInset === undefined
    ? undefined
    : ({
        '--forged-content-inset': `${contentInset}px`,
        '--forged-interactive-inset': `${interactiveInset ?? contentInset}px`,
      } as CSSProperties)
  return (
    <View
      className={reconstructionClass(reconstructionStyle('forgedPanel'), toneClass[tone], className)}
      data-content-inset={contentInset}
      data-frame-safe-area={contentInset === undefined ? 'false' : 'true'}
      data-frame-layer={frameLayer}
      data-frame-mode={frameMode}
      data-frame-asset-ready={frameAssetReady ? 'true' : 'false'}
      data-frame-asset-id={assetId}
      data-frame-width={frameWidth}
      data-interactive-inset={interactiveInset ?? contentInset}
      data-material-family={materialFamily}
      data-owner={owner}
      data-region={region}
      data-tone={tone}
      style={safeAreaStyle ?? {}}
      {...(onClick ? { onClick } : {})}
    >
      {frameMode === 'material' ? (
        <NineSliceFrame
          assetId={assetId}
          className={reconstructionStyle(frameLayer === 'overlay' ? 'forgedPanelFrameOverlay' : 'forgedPanelFrameBehind')}
          frameWidth={frameWidth}
          slotId={slotId}
        />
      ) : null}
      {children}
    </View>
  )
}

export interface LayeredSurfaceProps {
  children: ReactNode
  decoration: ReactNode
  reservedInlineStart: number
  className?: string | undefined
  decorationClassName?: string | undefined
  contentClassName?: string | undefined
}

export function LayeredSurface({
  children,
  decoration,
  reservedInlineStart,
  className,
  decorationClassName,
  contentClassName,
}: LayeredSurfaceProps) {
  const style = { '--layered-reserved-inline-start': `${reservedInlineStart}px` } as CSSProperties
  return (
    <View
      className={reconstructionClass(reconstructionStyle('layeredSurface'), className)}
      data-layered-surface="true"
      style={style}
    >
      <View
        className={reconstructionClass(reconstructionStyle('layeredSurfaceDecoration'), decorationClassName)}
        data-layer="decoration"
      >
        {decoration}
      </View>
      <View
        className={reconstructionClass(reconstructionStyle('layeredSurfaceContent'), contentClassName)}
        data-layer="content"
      >
        {children}
      </View>
    </View>
  )
}

export interface SectionHeadingProps {
  title: string
  detail?: string | undefined
  action?: ReactNode | undefined
}

export function SectionHeading({ title, detail, action }: SectionHeadingProps) {
  return (
    <View className={reconstructionStyle('sectionHeading')} data-owner="section-heading">
      <View className={reconstructionStyle('sectionHeadingCopy')}>
        <Text className={reconstructionStyle('sectionTitle')} data-role="section-heading-title">{title}</Text>
        {detail ? <Text className={reconstructionStyle('sectionDetail')} data-role="section-heading-detail">{detail}</Text> : null}
      </View>
      {action ? <View className={reconstructionStyle('sectionAction')}>{action}</View> : null}
    </View>
  )
}

export interface RouteStatePanelProps {
  state: ReadinessState
  title: string
  detail: string
  compact?: boolean | undefined
  variant?: 'inline' | 'page' | undefined
  region?: string | undefined
  emblemAssetId?: ProductionAssetId | undefined
  showAssets?: boolean | undefined
  actionLabel?: string | undefined
  onAction?: (() => void) | undefined
}

export function RouteStatePanel({
  state,
  title,
  detail,
  compact = false,
  variant = 'inline',
  region = 'shared_route-state-panel',
  emblemAssetId,
  showAssets = true,
  actionLabel,
  onAction,
}: RouteStatePanelProps) {
  if (variant === 'page') {
    return (
      <ForgedPanel
        className={reconstructionStyle('routeStatePagePanel')}
        contentInset={14}
        frameWidth={10}
        interactiveInset={14}
        owner="route-state-panel"
        region={region}
        tone={state === 'error' || state === 'blocked' ? 'blocked' : 'inset'}
      >
        <View className={reconstructionStyle('routeStatePage')} data-frame-content="true" data-role="route-state">
          {emblemAssetId ? (
            <ProductionAssetImage
              alt="状态徽记"
              assetId={emblemAssetId}
              className={reconstructionStyle('routeStateEmblem')}
              enabled={showAssets}
              slotId="asset_slot.empty-state-emblem"
            />
          ) : <StatusVisual state={state} variant="pill" />}
          <View className={reconstructionStyle('routeStateCopy')}>
            <Text className={reconstructionStyle('routeStateTitle')}>{title}</Text>
            <Text className={reconstructionStyle('routeStateDetail')}>{detail}</Text>
          </View>
          {actionLabel && onAction ? (
            <View className={reconstructionStyle('routeStateAction')}>
              <ActionButton variant="secondaryMetal" onClick={onAction}>{actionLabel}</ActionButton>
            </View>
          ) : null}
        </View>
      </ForgedPanel>
    )
  }
  return (
    <View className={reconstructionClass(reconstructionStyle('routeStatePanel'), compact && reconstructionStyle('routeStateCompact'))}>
      <StatusVisual glyph="row" state={state} variant="pill" />
      <View>
        <Text className={reconstructionStyle('routeStateTitle')}>{title}</Text>
        <Text className={reconstructionStyle('routeStateDetail')}>{detail}</Text>
      </View>
    </View>
  )
}
