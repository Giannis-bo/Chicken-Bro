import { Text, View } from '@tarojs/components'
import type { ReactNode } from 'react'

import { ActionButton } from './ActionButton'
import { ProductionAssetImage } from './ProductionAsset'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { SystemGlyph } from './SystemGlyph'
import { resolvePageChromeMode, type PageFrameVariant } from './PageFrame.chrome'
import { reconstructionStyle } from './reconstruction-style'
import { ownerClass, ownerStyle } from './style'

export type { PageChromeMode, PageFrameVariant } from './PageFrame.chrome'

export interface PageFrameProps {
  children: ReactNode
  title: string
  kicker?: string | undefined
  description?: string | undefined
  size?: 'compact' | 'standard' | 'large' | undefined
  stickyHeader?: boolean | undefined
  onBack?: (() => void) | undefined
  backRegion?: string | undefined
  onRefresh?: (() => void) | undefined
  rightAction?: ReactNode | undefined
  sourceLabel?: string | undefined
  headerStatusLabel?: string | undefined
  variant?: PageFrameVariant | undefined
  region?: string | undefined
}

export function PageFrame({
  children,
  title,
  kicker,
  description,
  size = 'standard',
  stickyHeader = false,
  onBack,
  backRegion,
  onRefresh,
  rightAction,
  sourceLabel,
  headerStatusLabel,
  variant = 'default',
  region = 'shared_page-frame',
}: PageFrameProps) {
  const chromeMode = resolvePageChromeMode(variant, onBack)
  const pushed = chromeMode === 'pushed' || chromeMode === 'pushed-action' || chromeMode === 'chat'
  const labeledBack = variant === 'build-intel'

  const titleNode = (
    <View className={reconstructionStyle('pageCenteredCopy')}>
      {kicker ? <Text className={reconstructionStyle('pageKicker')}>{kicker}</Text> : null}
      <Text
        className={ownerClass(reconstructionStyle('pageTitle'), ownerStyle('pageFrameTitleText'))}
        data-role="page-title"
      >
        {title}
      </Text>
    </View>
  )
  const pushedTitleNode = variant === 'chickenbro-chat' ? (
    <View className={reconstructionStyle('chickenbroHeaderIdentity')} data-slot-id="asset_slot.chickenbro-header-identity">
      <View className={reconstructionStyle('chickenbroHeaderMedallion')}>
        <ProductionAssetGlyph
          assetId="mascot-shell-family.captain"
          className={reconstructionStyle('chickenbroHeaderGlyph')}
          fallbackAssetId="utility-glyph-family.assistant"
          fallbackSlotId="asset_slot.utility-glyph-family"
          slotId="asset_slot.chickenbro-header-identity"
        />
      </View>
      {titleNode}
    </View>
  ) : titleNode
  const rootContextNode = sourceLabel || headerStatusLabel ? (
    variant === 'news-home' && sourceLabel && headerStatusLabel ? (
      <View className={reconstructionStyle('headerEvidenceSocket')} data-role="header-source-status">
        <Text className={reconstructionStyle('headerEvidenceSource')}>{sourceLabel}</Text>
        <Text className={reconstructionStyle('headerEvidenceDivider')}>：</Text>
        <Text className={reconstructionStyle('headerEvidenceStatus')}>{headerStatusLabel}</Text>
        <SystemGlyph
          assetId="source-badge-family.information"
          className={reconstructionStyle('headerEvidenceGlyph')}
          slotId="asset_slot.source-badge-family"
        />
      </View>
    ) : headerStatusLabel ? (
      <View className={reconstructionStyle('headerStatusSocket')} data-role="header-status">
        <View className={reconstructionStyle('headerStatusDot')} />
        <Text className={reconstructionStyle('headerStatusLabel')}>{headerStatusLabel}</Text>
      </View>
    ) : (
      <View className={reconstructionStyle('headerSourceSocket')}>
        <SystemGlyph
          assetId="utility-glyph-family.source-link"
          className={reconstructionStyle('headerSourceGlyph')}
          slotId="asset_slot.utility-glyph-family"
        />
        <Text className={reconstructionStyle('headerSourceLabel')}>{sourceLabel}</Text>
      </View>
    )
  ) : null

  return (
    <View
      className={ownerClass(
        ownerStyle('pageFrameOwner'),
        ownerStyle(`pageFrame-${chromeMode}`),
      )}
      data-owner="page-frame"
      data-chrome-mode={chromeMode}
      data-size={size}
      data-variant={variant}
    >
      <View
        className={ownerClass(
          ownerStyle('pageFrameHeader'),
          stickyHeader && ownerStyle('pageFrameHeaderSticky'),
        )}
        data-chrome-owner="page-frame"
        data-layout-mode={chromeMode}
        data-root-header-layout={!pushed ? 'inline' : undefined}
        data-region={region}
        data-route-variant={variant}
      >
        <View className={ownerStyle('pageFrameHeaderLeading')}>
          {pushed ? (
            <View
              className={ownerStyle('pageFrameBackControl')}
              data-role="pushed-back-control"
              {...(backRegion ? { 'data-region': backRegion } : {})}
            >
              <ProductionAssetImage
                alt="返回按钮框"
                assetId="pushed-back-medallion.default"
                className={ownerStyle('pageFrameBackMedallion')}
                slotId="asset_slot.pushed-back-medallion"
              />
              <ActionButton
                ariaLabel="返回"
                className={ownerStyle('pageFrameBackButton')}
                variant="ghost"
                onClick={onBack}
              >
                <SystemGlyph
                  assetId="utility-glyph-family.chevron-right"
                  className={ownerStyle('pageFrameBackGlyph')}
                  slotId="asset_slot.utility-glyph-family"
                />
                {labeledBack ? <Text className={ownerStyle('pageFrameBackLabel')}>返回</Text> : null}
              </ActionButton>
            </View>
          ) : titleNode}
        </View>

        {pushed ? (
          <View className={ownerStyle('pageFrameHeaderTitle')} data-role="page-centered-title">
            <View
              className={ownerClass(
                ownerStyle('pageFrameTitleRail'),
                ownerStyle('pageFrameTitleRailLeft'),
              )}
              data-ornament-side="left"
            />
            {pushed ? pushedTitleNode : titleNode}
            <View
              className={ownerClass(
                ownerStyle('pageFrameTitleRail'),
                ownerStyle('pageFrameTitleRailRight'),
              )}
              data-ornament-side="right"
            />
          </View>
        ) : (
          <View className={ownerStyle('pageFrameRootContext')} data-role="page-root-context">
            {rootContextNode}
          </View>
        )}

        <View className={ownerStyle('pageFrameHeaderAction')} data-role="header-action">
          {rightAction ?? (onRefresh ? (
            <View className={reconstructionStyle('headerActionSocket')}>
              <ActionButton ariaLabel="刷新" variant="ghost" onClick={onRefresh}>
                <SystemGlyph
                  assetId="utility-glyph-family.reset"
                  className={reconstructionStyle('headerActionGlyph')}
                  slotId="asset_slot.utility-glyph-family"
                />
              </ActionButton>
            </View>
          ) : null)}
        </View>
      </View>
      {description ? <Text className={reconstructionStyle('pageDescription')}>{description}</Text> : null}
      {children}
    </View>
  )
}
