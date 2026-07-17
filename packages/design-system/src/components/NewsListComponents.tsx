import { Text, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import type { ReadinessState } from '@wow-mini/domain'

import { ActionContent } from './ActionContent'
import { ActionButton } from './ActionButton'
import { ProductionAssetImage } from './ProductionAsset'
import { ForgedPanel } from './ReconstructionPrimitives'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'

export interface NewsListSummaryProps {
  title: string
  countLabel: string
  stateLabel: string
  loading?: boolean
  onRefresh: () => void
}

export function NewsListSummary({
  title,
  countLabel,
  stateLabel,
  loading = false,
  onRefresh,
}: NewsListSummaryProps) {
  return (
    <View className={reconstructionStyle('newsListSummaryOwner')} data-owner="news-list-summary">
      <View className={reconstructionStyle('newsListSummaryCopy')}>
        <Text className={reconstructionStyle('newsListSummaryTitle')} data-role="news-list-summary-title">{title}</Text>
        <Text className={reconstructionStyle('newsListSummaryCount')} data-role="news-list-summary-count">
          {countLabel} · {stateLabel}
        </Text>
      </View>
      <View className={reconstructionStyle('newsListSummaryAction')}>
        <ActionButton ariaLabel="刷新资讯列表" disabled={loading} variant="secondaryMetal" onClick={onRefresh}>
          <ActionContent className={reconstructionStyle('newsListSummaryActionContent')}>
            <SystemGlyph
              assetId="utility-glyph-family.reset"
              className={reconstructionStyle('newsListSummaryActionGlyph')}
              slotId="asset_slot.utility-glyph-family"
            />
            <Text>{loading ? '刷新中' : '刷新列表'}</Text>
          </ActionContent>
        </ActionButton>
      </View>
    </View>
  )
}

export interface NewsListCategoryItem {
  id: string
  label: string
}

export interface NewsListCategoryFilterProps {
  items: readonly NewsListCategoryItem[]
  activeId: string
  sortDirection: 'newest' | 'oldest'
  sortLabel: string
  loading?: boolean
  onSelect: (item: NewsListCategoryItem) => void
  onSort: () => void
}

export function NewsListCategoryFilter({
  items,
  activeId,
  sortDirection,
  sortLabel,
  loading = false,
  onSelect,
  onSort,
}: NewsListCategoryFilterProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsListCategoryOwner')}
      contentInset={3}
      frameAssetId="news-frame.tab"
      frameSlotId="asset_slot.news-frame"
      frameWidth={0}
      materialFamily="news"
      owner="news-list-category-filter"
      region="category_filter_bar"
    >
      <View className={reconstructionStyle('newsListCategoryGrid')} data-frame-content="true">
        {items.map((item) => {
          const selected = item.id === activeId
          return (
            <View
              key={item.id}
              aria-label={`${item.label}分类`}
              className={reconstructionClass(
                reconstructionStyle('newsListCategoryItemOwner'),
                selected && reconstructionStyle('newsListCategoryItemOwnerActive'),
              )}
              data-role="news-list-category"
              data-selected={selected ? 'true' : 'false'}
              onClick={() => !loading && onSelect(item)}
            >
              {loading ? (
                <View className={reconstructionStyle('newsListCategorySkeleton')} />
              ) : (
                <Text>{item.label}</Text>
              )}
              {selected ? <View className={reconstructionStyle('newsListCategoryUnderline')} /> : null}
            </View>
          )
        })}
        <View
          aria-label={sortLabel}
          className={reconstructionClass(
            reconstructionStyle('newsListSortControl'),
            reconstructionStyle(sortDirection === 'newest' ? 'newsListSortNewest' : 'newsListSortOldest'),
          )}
          data-role="news-list-sort"
          data-sort-direction={sortDirection}
          onClick={() => !loading && onSort()}
        >
          <SystemGlyph assetId="utility-glyph-family.filter" slotId="asset_slot.utility-glyph-family" />
        </View>
      </View>
    </ForgedPanel>
  )
}

export interface NewsListFeedItem {
  id: string
  title: string
  sourceLabel: string
  sourceAvailable: boolean
  status: ReadinessState
  statusLabel: string
  dateLabel: string
  accent: 'blue' | 'gold'
}

export interface NewsListFeedProps {
  items: readonly NewsListFeedItem[]
  loading?: boolean
  loadingRows?: number
  onSelect: (item: NewsListFeedItem) => void
}

export function NewsListFeed({
  items,
  loading = false,
  loadingRows = 6,
  onSelect,
}: NewsListFeedProps) {
  const rows = loading
    ? Array.from({ length: loadingRows }, (_, index): NewsListFeedItem => ({
        id: `loading-${index + 1}`,
        title: '',
        sourceLabel: '',
        sourceAvailable: false,
        status: 'loading',
        statusLabel: '',
        dateLabel: '',
        accent: index % 3 === 2 ? 'gold' : 'blue',
      }))
    : items
  // Loading keeps the target's six skeleton lanes. Once truth is available,
  // the feed owns exactly the returned rows so sparse payloads do not leave
  // invisible grid tracks and a large empty hole above the terminal panel.
  const rowStyle = {
    '--news-list-row-count': Math.max(rows.length, loading ? loadingRows : 0, 1),
  } as CSSProperties

  return (
    <ForgedPanel
      className={reconstructionStyle('newsListFeedOwner')}
      contentInset={4}
      frameAssetId="news-frame.feed"
      frameSlotId="asset_slot.news-frame"
      frameWidth={0}
      materialFamily="news"
      owner="news-list-feed"
      region="news_results_list"
    >
      <View
        className={reconstructionStyle('newsListFeedRows')}
        data-frame-content="true"
        data-loading={loading ? 'true' : 'false'}
        style={rowStyle}
      >
        {rows.map((item, index) => (
          <View
            key={item.id}
            className={reconstructionStyle('newsListFeedRow')}
            data-accent={item.accent}
            data-item-id={item.id}
            data-region={`news-list_target_region_feed-card-${index + 1}`}
            data-role="news-list-feed-card"
            onClick={() => !loading && onSelect(item)}
          >
            <View className={reconstructionStyle('newsListFeedRail')} data-role="news-list-feed-rail" />
            <View
              className={reconstructionStyle('newsListDocumentMedallion')}
              data-role="news-list-document-medallion"
              data-slot-id="asset_slot.news-list-document-medallion"
            >
              <ProductionAssetImage
                alt="资讯文档徽章"
                assetId="news-list-document-medallion.default"
                className={reconstructionStyle('newsListDocumentMedallionAsset')}
                slotId="asset_slot.news-list-document-medallion"
              />
              <SystemGlyph
                assetId="utility-glyph-family.document"
                className={reconstructionStyle('newsListDocumentMedallionGlyph')}
                dataRole="news-list-document-glyph"
                slotId="asset_slot.utility-glyph-family"
              />
            </View>
            <View className={reconstructionStyle('newsListFeedCopy')}>
              {loading ? (
                <>
                  <View className={reconstructionStyle('newsListSkeletonTitle')} />
                  <View className={reconstructionStyle('newsListSkeletonMeta')} />
                </>
              ) : (
                <>
                  <Text className={reconstructionStyle('newsListFeedRowTitle')} data-role="news-list-feed-title">{item.title}</Text>
                  <View className={reconstructionStyle('newsListFeedMeta')}>
                    <View
                      className={reconstructionClass(
                        reconstructionStyle('newsListFeedSource'),
                        !item.sourceAvailable && reconstructionStyle('newsListFeedSourceBlocked'),
                      )}
                      data-role="news-list-source-plate"
                      data-source-available={item.sourceAvailable ? 'true' : 'false'}
                    >
                      <SystemGlyph
                        assetId="utility-glyph-family.source-link"
                        slotId="asset_slot.utility-glyph-family"
                      />
                      <Text data-role="source-reference-label">{item.sourceLabel}</Text>
                    </View>
                    <StatusVisual
                      compact
                      glyph="row"
                      label={item.statusLabel}
                      state={item.status}
                      variant="pill"
                    />
                  </View>
                </>
              )}
            </View>
            <View className={reconstructionStyle('newsListFeedTrailing')}>
              {loading ? (
                <View className={reconstructionStyle('newsListSkeletonDate')} />
              ) : (
                <>
                  <SystemGlyph
                    assetId="utility-glyph-family.chevron-right"
                    dataRole="news-list-feed-chevron"
                    slotId="asset_slot.utility-glyph-family"
                  />
                  <Text className={reconstructionStyle('newsListFeedDate')} data-role="news-list-feed-date">{item.dateLabel}</Text>
                </>
              )}
            </View>
          </View>
        ))}
      </View>
    </ForgedPanel>
  )
}

export type NewsListTerminalMode = 'loading' | 'more' | 'complete' | 'empty' | 'error' | 'blocked'

export interface NewsListTerminalPanelProps {
  mode: NewsListTerminalMode
  title: string
  detail: string
  actionLabel?: string
  onAction?: () => void
}

const terminalGlyph: Readonly<Record<NewsListTerminalMode, string>> = {
  loading: 'utility-glyph-family.runtime',
  more: 'utility-glyph-family.plus',
  complete: 'utility-glyph-family.shield',
  empty: 'utility-glyph-family.document',
  error: 'utility-glyph-family.warning',
  blocked: 'utility-glyph-family.warning',
}

export function NewsListTerminalPanel({
  mode,
  title,
  detail,
  actionLabel,
  onAction,
}: NewsListTerminalPanelProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsListTerminalOwner')}
      contentInset={12}
      frameAssetId="news-frame.panel"
      frameSlotId="asset_slot.news-frame"
      frameWidth={0}
      materialFamily="news"
      owner="news-list-terminal-panel"
      region="empty_state_panel"
      tone={mode === 'error' || mode === 'blocked' ? 'blocked' : 'inset'}
    >
      <View
        className={reconstructionStyle('newsListTerminalContent')}
        data-frame-content="true"
        data-has-action={actionLabel && onAction ? 'true' : 'false'}
        data-terminal-mode={mode}
      >
        <View
          className={reconstructionStyle('newsListTerminalEmblem')}
          data-role="news-list-terminal-emblem"
          data-slot-id="asset_slot.news-list-terminal-emblem"
        >
          <ProductionAssetImage
            alt="资讯列表终止状态徽章框"
            assetId="news-list-terminal-medallion.default"
            className={reconstructionStyle('newsListTerminalEmblemAsset')}
            slotId="asset_slot.news-list-terminal-emblem"
          />
          <View className={reconstructionStyle('newsListTerminalEmblemCore')}>
            <SystemGlyph assetId={terminalGlyph[mode]} slotId="asset_slot.utility-glyph-family" />
          </View>
        </View>
        <View className={reconstructionStyle('newsListTerminalCopy')}>
          <Text className={reconstructionStyle('newsListTerminalTitle')}>{title}</Text>
          <Text className={reconstructionStyle('newsListTerminalDetail')}>{detail}</Text>
        </View>
        {actionLabel && onAction ? (
          <View className={reconstructionStyle('newsListTerminalAction')} data-role="news-list-terminal-action">
            <ActionButton variant="secondaryMetal" onClick={onAction}>{actionLabel}</ActionButton>
          </View>
        ) : <View className={reconstructionStyle('newsListTerminalActionSpacer')} />}
      </View>
    </ForgedPanel>
  )
}

export interface TrustDisclaimerProps {
  copy?: string
}

export function TrustDisclaimer({ copy = '内容仅供参考，请以原始来源为准' }: TrustDisclaimerProps) {
  return (
    <View className={reconstructionStyle('newsListTrustDisclaimer')} data-owner="trust-disclaimer">
      <View className={reconstructionStyle('newsListTrustFastener')} data-role="news-list-trust-fastener" />
      <View className={reconstructionStyle('newsListTrustCopy')}>
        <SystemGlyph assetId="utility-glyph-family.shield" slotId="asset_slot.utility-glyph-family" />
        <Text>{copy}</Text>
      </View>
      <View className={reconstructionStyle('newsListTrustFastener')} data-role="news-list-trust-fastener" />
    </View>
  )
}
