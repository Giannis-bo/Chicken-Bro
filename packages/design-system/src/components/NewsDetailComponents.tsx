import { ScrollView, Text, View } from '@tarojs/components'

import type { NewsBodyBlock, ReadinessState } from '@wow-mini/domain'

import { ActionContent } from './ActionContent'
import { ActionButton } from './ActionButton'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ProductionAssetImage } from './ProductionAsset'
import { ForgedPanel } from './ReconstructionPrimitives'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'

export interface NewsDetailHeroProps {
  title: string
  sourceLabel: string
  state: ReadinessState
  stateLabel: string
  loading?: boolean
}

export function NewsDetailHero({
  title,
  sourceLabel,
  state,
  stateLabel,
  loading = false,
}: NewsDetailHeroProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsDetailHeroOwner')}
      contentInset={12}
      frameAssetId="news-frame.panel"
      frameSlotId="asset_slot.news-detail-frame-family"
      frameWidth={0}
      frameMode="none"
      materialFamily="news"
      owner="news-detail-hero"
      region="article_header_card"
      tone="raised"
    >
      <View className={reconstructionStyle('newsDetailHeroContent')} data-frame-content="true">
        {loading ? (
          <>
            <View className={reconstructionStyle('newsDetailHeroTitleSkeleton')} />
            <View className={reconstructionStyle('newsDetailHeroSourceSkeleton')} />
            <View className={reconstructionStyle('newsDetailHeroStatusSkeleton')} />
          </>
        ) : (
          <>
            <Text className={reconstructionStyle('newsDetailHeroTitle')} data-role="news-detail-title">{title}</Text>
            <View className={reconstructionStyle('newsDetailHeroSourceRow')}>
              <View
                className={reconstructionStyle('newsDetailSourceCrest')}
                data-role="news-detail-source-crest"
                data-slot-id="asset_slot.news-detail-source-crest"
              >
                <ProductionAssetImage
                  alt="来源参考徽章框"
                  assetId="news-detail-source-crest.default"
                  className={reconstructionStyle('newsDetailSourceCrestAsset')}
                  slotId="asset_slot.news-detail-source-crest"
                />
                <View className={reconstructionStyle('newsDetailSourceCrestCore')}>
                  <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.utility-glyph-family" />
                </View>
              </View>
              <View className={reconstructionStyle('newsDetailHeroSourceCopy')}>
                <Text className={reconstructionStyle('newsDetailHeroSourceEyebrow')}>来源参考</Text>
                <Text className={reconstructionStyle('newsDetailHeroSourceLabel')} data-role="news-detail-source">{sourceLabel}</Text>
              </View>
            </View>
            <View className={reconstructionStyle('newsDetailHeroVerification')}>
              <StatusVisual compact glyph="row" label={stateLabel} state={state} variant="pill" />
            </View>
          </>
        )}
      </View>
    </ForgedPanel>
  )
}

export interface TranslationStatusSegment {
  id: string
  label: string
  selected: boolean
}

export interface TranslationStatusSegmentsProps {
  items: readonly TranslationStatusSegment[]
  activeId: string
  loading?: boolean
}

export function TranslationStatusSegments({
  items,
  activeId,
  loading = false,
}: TranslationStatusSegmentsProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsDetailTranslationOwner')}
      contentInset={3}
      frameAssetId="news-frame.tab"
      frameSlotId="asset_slot.news-detail-frame-family"
      frameWidth={0}
      frameMode="none"
      materialFamily="news"
      owner="translation-status-segments"
      region="translation_status"
    >
      <View className={reconstructionStyle('newsDetailTranslationContent')} data-frame-content="true">
        <Text className={reconstructionStyle('newsDetailTranslationLabel')} data-role="news-detail-translation-label">翻译状态</Text>
        <View className={reconstructionStyle('newsDetailTranslationSegments')} data-active-id={activeId}>
          {items.map((item) => (
            <View
              key={item.id}
              className={reconstructionClass(
                reconstructionStyle('newsDetailTranslationSegment'),
                item.selected && reconstructionStyle('newsDetailTranslationSegmentActive'),
              )}
              data-role="news-detail-translation-segment"
              data-selection-material={item.selected ? 'active' : 'inactive'}
              data-segment-id={item.id}
              data-selected={item.selected ? 'true' : 'false'}
            >
              {loading ? <View className={reconstructionStyle('newsDetailTranslationSkeleton')} /> : <Text>{item.label}</Text>}
            </View>
          ))}
        </View>
      </View>
    </ForgedPanel>
  )
}

export interface ArticleReadingSurfaceProps {
  blocks: readonly NewsBodyBlock[]
  loading?: boolean
}

function ArticleBodyBlock({ block, index }: { block: NewsBodyBlock; index: number }) {
  const type = block.type || 'paragraph'
  if (type === 'list') {
    return (
      <View className={reconstructionStyle('newsDetailBodyBlock')} data-block-index={index} data-block-type="list" data-role="article-body-block">
        {(block.items ?? []).map((item, itemIndex) => (
          <Text key={`${index}-${itemIndex}`} className={reconstructionStyle('newsDetailBodyListItem')}>• {item}</Text>
        ))}
      </View>
    )
  }
  return (
    <View
      className={reconstructionClass(
        reconstructionStyle('newsDetailBodyBlock'),
        type === 'heading' && reconstructionStyle('newsDetailBodyHeading'),
        type === 'quote' && reconstructionStyle('newsDetailBodyQuote'),
      )}
      data-block-index={index}
      data-block-type={type}
      data-role="article-body-block"
    >
      <Text>{block.text ?? ''}</Text>
    </View>
  )
}

export function ArticleReadingSurface({ blocks, loading = false }: ArticleReadingSurfaceProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsDetailReadingOwner')}
      contentInset={11}
      frameAssetId="news-frame.feed"
      frameSlotId="asset_slot.news-detail-frame-family"
      frameWidth={0}
      frameMode="none"
      materialFamily="news"
      owner="article-reading-surface"
      region="article_body"
      tone="inset"
    >
      <ScrollView
        className={reconstructionStyle('newsDetailReadingScroll')}
        data-body-block-count={blocks.length}
        data-frame-content="true"
        data-role="article-reading-scroll"
        scrollY
      >
        <View className={reconstructionClass(
          reconstructionStyle('newsDetailReadingContent'),
          !loading && blocks.length === 0 && reconstructionStyle('newsDetailReadingContentEmpty'),
        )}>
          {loading ? Array.from({ length: 8 }, (_, index) => (
            <View
              key={`body-loading-${index}`}
              className={reconstructionClass(
                reconstructionStyle('newsDetailBodySkeleton'),
                index % 3 === 2 && reconstructionStyle('newsDetailBodySkeletonShort'),
              )}
            />
          )) : blocks.length ? blocks.map((block, index) => (
            <ArticleBodyBlock key={`${block.type}-${index}`} block={block} index={index} />
          )) : (
            <View className={reconstructionStyle('newsDetailReadingEmpty')} data-role="article-body-empty">
              <View className={reconstructionStyle('newsDetailReadingEmptyEmblem')}>
                <SystemGlyph assetId="utility-glyph-family.document" slotId="asset_slot.utility-glyph-family" />
              </View>
              <View className={reconstructionStyle('newsDetailReadingEmptyCopy')}>
                <Text className={reconstructionStyle('newsDetailReadingEmptyTitle')}>正文暂不可用</Text>
                <Text className={reconstructionStyle('newsDetailReadingEmptyDetail')}>当前没有可验证的文章正文，页面不会填充未经来源确认的内容。</Text>
              </View>
              <View className={reconstructionStyle('newsDetailReadingEmptyFacts')}>
                <View><Text>来源状态</Text><Text>未获得正文</Text></View>
                <View><Text>展示策略</Text><Text>不填充未验证内容</Text></View>
                <View><Text>可用操作</Text><Text>返回资讯列表选择文章</Text></View>
              </View>
            </View>
          )}
        </View>
      </ScrollView>
    </ForgedPanel>
  )
}

export interface SourceReferenceActionProps {
  sourceLabel: string
  sourceUrlLabel: string
  available: boolean
  onCopy?: () => void
}

export function SourceReferenceAction({
  sourceLabel,
  sourceUrlLabel,
  available,
  onCopy,
}: SourceReferenceActionProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsDetailSourceActionOwner')}
      contentInset={8}
      frameAssetId="news-frame.panel"
      frameSlotId="asset_slot.news-detail-frame-family"
      frameWidth={0}
      frameMode="none"
      materialFamily="news"
      owner="source-reference-action"
      region="source_reference_action"
    >
      <View className={reconstructionStyle('newsDetailSourceActionContent')} data-frame-content="true">
        <View className={reconstructionStyle('newsDetailSourceActionGlyphSocket')} data-role="news-detail-source-action-glyph">
          <SystemGlyph
            assetId="utility-glyph-family.source-link"
            className={reconstructionStyle('newsDetailSourceActionGlyph')}
            slotId="asset_slot.news-detail-source-actions"
          />
        </View>
        <View className={reconstructionStyle('newsDetailSourceActionCopy')}>
          <Text className={reconstructionStyle('newsDetailSourceActionHeading')}>来源参考 · {sourceLabel}</Text>
          <Text className={reconstructionStyle('newsDetailSourceActionUrl')} data-role="news-detail-source-url">{sourceUrlLabel}</Text>
        </View>
        <View
          className={reconstructionStyle('newsDetailSourceActionButton')}
          data-available={available ? 'true' : 'false'}
          data-role="news-detail-source-action-button"
        >
          <ActionButton ariaLabel="复制来源链接" disabled={!available} variant="secondaryMetal" {...(available && onCopy ? { onClick: onCopy } : {})}>
            <ActionContent className={reconstructionStyle('newsDetailSourceActionButtonContent')}>
              <SystemGlyph assetId="utility-glyph-family.copy" slotId="asset_slot.news-detail-source-actions" />
              <Text>{available ? '复制来源' : '来源不可用'}</Text>
            </ActionContent>
          </ActionButton>
        </View>
      </View>
    </ForgedPanel>
  )
}

export interface ArticleEvidenceRow {
  id: string
  typeLabel: string
  summary: string
  statusLabel: string
  timeLabel: string
  state: ReadinessState
}

export interface ArticleEvidencePanelProps {
  rows: readonly ArticleEvidenceRow[]
  expanded: boolean
  onToggle: () => void
}

export function ArticleEvidencePanel({ rows, expanded, onToggle }: ArticleEvidencePanelProps) {
  return (
    <ForgedPanel
      className={reconstructionStyle('newsDetailEvidenceOwner')}
      contentInset={7}
      frameAssetId="news-frame.panel"
      frameSlotId="asset_slot.news-detail-frame-family"
      frameWidth={0}
      frameMode="none"
      materialFamily="news"
      owner="article-evidence-panel"
      region="evidence_details_panel"
      tone="inset"
    >
      <View className={reconstructionStyle('newsDetailEvidenceContent')} data-expanded={expanded ? 'true' : 'false'} data-frame-content="true" data-role="news-detail-evidence-content">
        <View className={reconstructionStyle('newsDetailEvidenceHeading')} data-role="news-detail-evidence-toggle" onClick={onToggle}>
          <View className={reconstructionStyle('newsDetailEvidenceHeadingGlyphSocket')} data-role="news-detail-evidence-heading-glyph-socket">
            <ProductionAssetGlyph
              assetId="news-metric-glyph.balance"
              className={reconstructionStyle('newsDetailEvidenceHeadingGlyph')}
              dataRole="news-detail-evidence-heading-glyph"
              fallbackAssetId="utility-glyph-family.adjust"
              fallbackSlotId="asset_slot.utility-glyph-family"
              slotId="asset_slot.news-metric-glyphs"
            />
          </View>
          <Text>证据明细</Text>
          <SystemGlyph
            assetId="news-detail-evidence-chevron.expanded"
            className={reconstructionClass(reconstructionStyle('newsDetailEvidenceChevron'), !expanded && reconstructionStyle('newsDetailEvidenceChevronCollapsed'))}
            slotId="asset_slot.news-detail-evidence-header"
          />
        </View>
        <View className={reconstructionStyle('newsDetailEvidenceBody')} data-role="news-detail-evidence-body">
          <View className={reconstructionStyle('newsDetailEvidenceColumns')}>
            <Text>类型</Text>
            <Text>内容摘要</Text>
            <Text>状态</Text>
            <Text>时间</Text>
          </View>
          {rows.length ? (
            <View className={reconstructionStyle('newsDetailEvidenceRows')} data-evidence-row-count={rows.length}>
              {rows.map((row) => (
                <View key={row.id} className={reconstructionStyle('newsDetailEvidenceRow')} data-evidence-id={row.id} data-role="news-detail-evidence-row">
                  <View className={reconstructionStyle('newsDetailEvidenceIdentity')} data-role="news-detail-evidence-identity" data-state={row.state}>
                    <View className={reconstructionStyle('newsDetailEvidenceIdentityMark')} />
                    <Text data-role="news-detail-evidence-type">{row.typeLabel}</Text>
                  </View>
                  <View className={reconstructionStyle('newsDetailEvidenceFact')} data-role="news-detail-evidence-fact">
                    <Text data-role="news-detail-evidence-summary">{row.summary}</Text>
                    <View className={reconstructionStyle('newsDetailEvidenceMeta')} data-role="news-detail-evidence-meta">
                      <Text data-role="news-detail-evidence-status" data-state={row.state}>{row.statusLabel}</Text>
                      <Text data-role="news-detail-evidence-time">{row.timeLabel}</Text>
                    </View>
                  </View>
                </View>
              ))}
            </View>
          ) : (
            <View className={reconstructionStyle('newsDetailEvidenceEmpty')} data-role="news-detail-evidence-empty">
              <View className={reconstructionStyle('newsDetailEvidenceEmptyEmblem')} data-slot-id="asset_slot.news-detail-evidence-emblem">
                <ProductionAssetImage
                  alt="证据空态徽章框"
                  assetId="news-detail-evidence-medallion.default"
                  className={reconstructionStyle('newsDetailEvidenceEmptyEmblemAsset')}
                  slotId="asset_slot.news-detail-evidence-emblem"
                />
                <View className={reconstructionStyle('newsDetailEvidenceEmptyEmblemCore')}>
                  <SystemGlyph assetId="utility-glyph-family.warning" slotId="asset_slot.utility-glyph-family" />
                </View>
              </View>
              <Text>暂无证据明细</Text>
            </View>
          )}
        </View>
      </View>
    </ForgedPanel>
  )
}

export type NewsDetailTerminalMode = 'loading' | 'ready' | 'missing' | 'error' | 'blocked'

export interface NewsDetailTerminalPanelProps {
  mode: NewsDetailTerminalMode
  title: string
  detail: string
  actionLabel?: string
  onAction?: () => void
}

const terminalGlyph: Readonly<Record<NewsDetailTerminalMode, string>> = {
  loading: 'utility-glyph-family.runtime',
  ready: 'utility-glyph-family.shield',
  missing: 'utility-glyph-family.warning',
  error: 'utility-glyph-family.warning',
  blocked: 'utility-glyph-family.warning',
}

export function NewsDetailTerminalPanel({
  mode,
  title,
  detail,
  actionLabel,
  onAction,
}: NewsDetailTerminalPanelProps) {
  const showAction = Boolean(actionLabel && onAction && mode === 'error')

  return (
    <ForgedPanel
      className={reconstructionStyle('newsDetailTerminalOwner')}
      contentInset={7}
      frameAssetId="news-frame.panel"
      frameSlotId="asset_slot.news-detail-frame-family"
      frameWidth={0}
      frameMode="none"
      materialFamily="news"
      owner="news-detail-terminal-panel"
      region="missing_article_state"
      tone={mode === 'error' || mode === 'blocked' ? 'blocked' : 'inset'}
    >
      <View
        className={reconstructionStyle('newsDetailTerminalContent')}
        data-frame-content="true"
        data-has-action={showAction ? 'true' : 'false'}
        data-terminal-mode={mode}
      >
        <View className={reconstructionStyle('newsDetailTerminalEmblem')} data-role="news-detail-terminal-emblem" data-slot-id="asset_slot.news-detail-terminal-emblem">
          <ProductionAssetImage
            alt="资讯详情终态徽章框"
            assetId="news-detail-terminal-medallion.default"
            className={reconstructionStyle('newsDetailTerminalEmblemAsset')}
            slotId="asset_slot.news-detail-terminal-emblem"
          />
          <View className={reconstructionStyle('newsDetailTerminalEmblemCore')}>
            <SystemGlyph assetId={terminalGlyph[mode]} slotId="asset_slot.utility-glyph-family" />
          </View>
        </View>
        <View className={reconstructionStyle('newsDetailTerminalCopy')}>
          <Text className={reconstructionStyle('newsDetailTerminalTitle')}>{title}</Text>
          <Text className={reconstructionStyle('newsDetailTerminalDetail')}>{detail}</Text>
        </View>
        {showAction ? (
          <View className={reconstructionStyle('newsDetailTerminalAction')}>
            <ActionButton variant="secondaryMetal" onClick={onAction}>{actionLabel}</ActionButton>
          </View>
        ) : <View className={reconstructionStyle('newsDetailTerminalSpacer')} />}
      </View>
    </ForgedPanel>
  )
}
