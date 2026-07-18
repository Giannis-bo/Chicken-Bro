import { Image, Picker, ScrollView, Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'
import type { CSSProperties } from 'react'

import type { ProductionAssetId } from '@wow-mini/assets-manifest'

import { resolveRuntimeMediaUrl } from '../runtime-media'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'
import { useTrustedMediaLoadState } from './useTrustedMediaLoadState'
import styles from './GearDetailComponents.module.scss'

function style(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function classes(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

interface TrustedGearMediaProps {
  iconUrl?: string | undefined
  label: string
  slotId?: string | undefined
  className?: string | undefined
  fallbackAssetId?: ProductionAssetId | undefined
  dataRole?: string | undefined
}

function TrustedGearMedia({
  iconUrl,
  label,
  slotId = 'asset_slot.gear-item-object',
  className,
  fallbackAssetId = 'quick-action-gear-glyph.default',
  dataRole,
}: TrustedGearMediaProps) {
  const trustedUrl = resolveRuntimeMediaUrl(iconUrl)
  const mediaLoadState = useTrustedMediaLoadState(trustedUrl)
  const visible = mediaLoadState.visible
  const mediaState = !trustedUrl ? 'fallback' : mediaLoadState.failed ? 'failed' : mediaLoadState.loaded ? 'loaded' : 'loading'
  return (
    <View
      className={classes(style('trustedMedia'), className)}
      data-media-state={mediaState}
      data-media-visible={visible ? 'true' : 'false'}
      data-role={dataRole}
      data-slot-id={slotId}
    >
      <View className={style('trustedFallback')}>
        <SystemGlyph assetId={fallbackAssetId} slotId={slotId} />
      </View>
      {trustedUrl ? (
        <Image
          aria-label={label}
          className={classes(style('trustedImage'), visible && style('trustedImageVisible'))}
          data-loaded={visible ? 'true' : 'false'}
          mode="aspectFill"
          src={trustedUrl}
          onError={mediaLoadState.onError}
          onLoad={mediaLoadState.onLoad}
        />
      ) : null}
    </View>
  )
}

export interface GearProfessionItem {
  id: string
  label: string
  selected: boolean
  iconUrl?: string | undefined
}

export interface GearProfessionSelectorProps {
  items: readonly GearProfessionItem[]
  loading?: boolean
  onSelect?: ((item: GearProfessionItem) => void) | undefined
}

export function GearProfessionSelector({ items, loading = false, onSelect }: GearProfessionSelectorProps) {
  const sourceItems: readonly GearProfessionItem[] = loading && items.length === 0
    ? [{ id: 'loading-current', label: '读取中', selected: false }]
    : items
  return (
    <View className={style('professionOwner')} data-owner="gear-profession-selector">
      <Text className={style('fieldLabel')}>职业</Text>
      <ScrollView className={style('professionScroll')} enhanced scrollX showScrollbar={false}>
        <View className={style('professionTrack')} data-role="gear-profession-track">
          {sourceItems.map((item) => (
            <ControlButton
              key={item.id}
              aria-label={`当前职业：${item.label}`}
              className={classes(
                style('professionButton'),
                loading && style('professionButtonLoading'),
              )}
              data-active={item.selected ? 'true' : 'false'}
              data-material-owner="css"
              data-selection-material={item.selected ? 'active' : 'inactive'}
              data-role="gear-profession-option"
              data-loading={loading ? 'true' : 'false'}
              data-profession-id={item.id}
              disabled={loading}
              onClick={() => onSelect?.(item)}
            >
              <TrustedGearMedia
                className={style('professionMedia')}
                dataRole="gear-class-medallion"
                fallbackAssetId="utility-glyph-family.shield"
                iconUrl={item.iconUrl}
                label={item.label}
                slotId="asset_slot.gear-class-medallion"
              />
              <Text className={style('professionName')}>{item.label}</Text>
            </ControlButton>
          ))}
        </View>
      </ScrollView>
    </View>
  )
}

export interface GearSpecializationItem {
  id: string
  label: string
}

export interface GearSpecializationSelectorProps {
  items: readonly GearSpecializationItem[]
  selectedIndex: number
  value: string
  loading?: boolean
  onSelect: (item: GearSpecializationItem) => void
}

export function GearSpecializationSelector({
  items,
  selectedIndex,
  value,
  loading = false,
  onSelect,
}: GearSpecializationSelectorProps) {
  return (
    <View className={style('specializationOwner')} data-owner="gear-specialization-selector">
      <Text className={style('fieldLabel')}>专精</Text>
      <Picker
        disabled={loading || items.length < 2}
        mode="selector"
        range={items.map((item) => item.label)}
        value={selectedIndex}
        onChange={(event) => {
          const item = items[Number(event.detail.value)]
          if (item) onSelect(item)
        }}
      >
        <View
          className={classes(style('specializationField'), loading && style('specializationFieldLoading'))}
          data-loading={loading ? 'true' : 'false'}
          data-role="gear-specialization-field"
        >
          <Text>{loading ? '读取中' : value || '待选择'}</Text>
          <View className={style('chevron')} />
        </View>
      </Picker>
    </View>
  )
}

export interface GearMetricItem {
  id: string
  label: string
  value: string
  verified: boolean
}

export interface GearReadinessOverviewProps {
  itemLevel: string
  itemLevelDetail: string
  readyCount: number
  requiredCount: number
  percent: number
  selectedCount: number
  state: string
  metrics: readonly GearMetricItem[]
}

export function GearReadinessOverview({
  itemLevel,
  itemLevelDetail,
  readyCount,
  requiredCount,
  percent,
  selectedCount,
  state,
  metrics,
}: GearReadinessOverviewProps) {
  const checkpoints = [
    { value: 0, label: '待配置' },
    { value: Math.ceil(requiredCount / 3), label: '起步' },
    { value: Math.ceil((requiredCount * 2) / 3), label: '接近' },
    { value: requiredCount, label: '就绪' },
  ]
  const progressStyle = { '--gear-ready-progress': `${Math.max(0, Math.min(100, percent))}%` } as CSSProperties
  return (
    <View
      className={style('readinessOwner')}
      data-owner="gear-readiness-overview"
      data-region="readiness_overview_panel"
      data-state={state}
      data-slot-id="asset_slot.gear-readiness-emblem"
    >
      <View className={style('levelEmblem')} data-role="gear-readiness-emblem">
        <View className={style('levelMechanicalCore')} data-role="gear-readiness-mechanical-core">
          <View /><View /><View />
        </View>
        <Text className={style('levelValue')} data-role="gear-item-level">{itemLevel}</Text>
        <Text className={style('levelLabel')}>平均装等</Text>
        <Text className={style('levelDetail')}>{itemLevelDetail}</Text>
      </View>
      <View className={style('readinessContent')}>
        <View className={style('readinessHeading')}>
          <Text>装备就绪度</Text>
          <Text data-role="gear-ready-count">{readyCount}/{requiredCount}</Text>
        </View>
        <View className={style('progress')} style={progressStyle} data-role="gear-readiness-progress" data-slot-id="asset_slot.gear-readiness-rail">
          <View className={style('progressTrack')} data-role="gear-readiness-track"><View className={style('progressFill')} /></View>
          {checkpoints.map((checkpoint) => (
            <View
              key={checkpoint.value}
              className={classes(style('progressNode'), readyCount >= checkpoint.value && style('progressNodeActive'))}
              data-active={readyCount >= checkpoint.value ? 'true' : 'false'}
              data-readiness-checkpoint={checkpoint.value}
            >
              <View className={style('progressSocket')} data-role="gear-readiness-socket" />
              <Text>{checkpoint.label}</Text>
            </View>
          ))}
        </View>
        <View className={style('readinessMeta')}>
          <Text data-role="gear-selected-count">{selectedCount ? `已配置 ${selectedCount} 件` : '尚未选择装备'}</Text>
          <Text>{state === 'ready' ? '可进入后续校验' : state === 'loading' ? '正在读取' : '部分证据'}</Text>
        </View>
        <Text className={style('metricsTitle')}>属性概览</Text>
        <View className={style('metricsGrid')}>
          {metrics.map((metric) => (
            <View
              key={metric.id}
              className={classes(style('metric'), metric.verified && style('metricVerified'))}
              data-verified={metric.verified ? 'true' : 'false'}
            >
              <Text>{metric.label}</Text>
              <Text>{metric.value}</Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  )
}

export interface GearEnhancementGroupItem {
  id: 'socket' | 'enchant' | 'embellishment'
  label: string
  optionCount: number
  value: string
  state: 'ready' | 'empty' | 'blocked'
}

const enhancementGlyph = {
  socket: 'gear-enhancement-glyph.gem',
  enchant: 'gear-enhancement-glyph.enchant-scroll',
  embellishment: 'gear-enhancement-glyph.ornament',
} as const

export function GearEnhancementBar({
  items,
  onSelect,
}: {
  items: readonly GearEnhancementGroupItem[]
  onSelect: (item: GearEnhancementGroupItem) => void
}) {
  return (
    <View className={style('enhancementOwner')} data-owner="gear-enhancement-bar" data-region="enhancement_categories_bar">
      {items.map((item) => (
        <ControlButton
          key={item.id}
          className={classes(
            style('enhancementItem'),
            style(`enhancementKind-${item.id}`),
            style(`enhancementState-${item.state}`),
          )}
          data-enhancement-kind={item.id}
          data-action-id={`open-${item.id}`}
          data-state={item.state}
          onClick={() => onSelect(item)}
        >
          <View className={style('enhancementMedallion')} data-role="gear-enhancement-medallion">
            <SystemGlyph assetId={enhancementGlyph[item.id]} slotId="asset_slot.gear-enhancement-medallions" />
          </View>
          <View className={style('enhancementCopy')}>
            <Text>{item.label}</Text>
            <Text>{item.value}</Text>
          </View>
          <View className={style('enhancementDot')} />
        </ControlButton>
      ))}
    </View>
  )
}

export interface GearWorkbenchSlotItem {
  slot: string
  label: string
  selected: boolean
  candidateCount: number
  itemId: string
  itemLabel: string
  levelLabel: string
  iconUrl?: string | undefined
  state: 'ready' | 'partial' | 'empty'
}

export interface GearWorkbenchCandidateItem {
  id: string
  label: string
  levelLabel: string
  sourceLabel: string
  statSummary: string
  badgeLabels: readonly string[]
  iconUrl?: string | undefined
  state: 'ready' | 'partial' | 'blocked'
}

export interface GearWorkbenchEnhancementItem {
  id: string
  kind: 'socket' | 'enchant' | 'embellishment'
  label: string
  iconUrl?: string | undefined
  selected: boolean
}

export interface GearSlotWorkbenchProps {
  slots: readonly GearWorkbenchSlotItem[]
  selectedSlot: string
  selectedSlotLabel: string
  candidateOpen?: boolean
  candidates: readonly GearWorkbenchCandidateItem[]
  enhancements: readonly GearWorkbenchEnhancementItem[]
  candidateLoading?: boolean
  notice?: string
  primaryLabel: string
  primaryDisabled?: boolean
  onSlot: (item: GearWorkbenchSlotItem) => void
  onCandidate: (item: GearWorkbenchCandidateItem) => void
  onClose: () => void
  onEnhancement: (item: GearWorkbenchEnhancementItem) => void
  onPrimary: () => void
}

const slotFallbackGlyph: Readonly<Record<string, ProductionAssetId>> = {
  head: 'gear-slot-silhouette.head',
  neck: 'gear-slot-silhouette.neck',
  shoulder: 'gear-slot-silhouette.shoulder',
  back: 'gear-slot-silhouette.back',
  chest: 'gear-slot-silhouette.chest',
  wrist: 'gear-slot-silhouette.wrist',
  hands: 'gear-slot-silhouette.hands',
  waist: 'gear-slot-silhouette.waist',
  legs: 'gear-slot-silhouette.legs',
  feet: 'gear-slot-silhouette.feet',
  finger1: 'gear-slot-silhouette.finger',
  finger2: 'gear-slot-silhouette.finger',
  trinket1: 'gear-slot-silhouette.trinket',
  trinket2: 'gear-slot-silhouette.trinket',
  main_hand: 'gear-slot-silhouette.main-hand',
  off_hand: 'gear-slot-silhouette.off-hand',
}

function GearSlotRow({
  item,
  side,
  onClick,
}: {
  item: GearWorkbenchSlotItem
  side: 'left' | 'right'
  onClick: () => void
}) {
  return (
    <ControlButton
      aria-label={`${item.label}：${item.itemLabel}`}
      className={classes(
        style('slotRow'),
        style(`slotRow-${item.state}`),
      )}
      data-active={item.selected ? 'true' : 'false'}
      data-material-owner="css"
      data-selection-material={item.selected ? 'active' : 'inactive'}
      data-side={side}
      data-state={item.state}
      data-slot-key={item.slot}
      data-role="gear-slot-row"
      onClick={onClick}
    >
      <TrustedGearMedia
        className={style('slotMedia')}
        dataRole="gear-slot-media"
        fallbackAssetId={slotFallbackGlyph[item.slot] ?? 'quick-action-gear-glyph.default'}
        iconUrl={item.iconUrl}
        label={item.itemLabel}
        slotId="asset_slot.gear-item-object"
      />
      <View className={style('slotCopy')}>
        <Text>{item.label}</Text>
        <Text>{item.itemLabel}</Text>
      </View>
      <Text className={style('slotLevel')}>{item.levelLabel || item.candidateCount}</Text>
    </ControlButton>
  )
}

export function GearSlotWorkbench({
  slots,
  selectedSlot,
  selectedSlotLabel,
  candidateOpen = false,
  candidates,
  enhancements,
  candidateLoading = false,
  notice = '',
  primaryLabel,
  primaryDisabled = false,
  onSlot,
  onCandidate,
  onClose,
  onEnhancement,
  onPrimary,
}: GearSlotWorkbenchProps) {
  const bySlot = new Map(slots.map((item) => [item.slot, item]))
  const leftSlotOrder = ['head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'main_hand', 'off_hand'] as const
  const rightSlotOrder = ['hands', 'waist', 'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2'] as const
  const left = leftSlotOrder.flatMap((slot) => {
    const item = bySlot.get(slot)
    return item ? [item] : []
  })
  const right = rightSlotOrder.flatMap((slot) => {
    const item = bySlot.get(slot)
    return item ? [item] : []
  })
  return (
    <View className={style('workbenchOwner')} data-owner="gear-slot-workbench" data-region="equipment_slots_panel">
      {candidateOpen ? (
        <View
          aria-label="关闭装备候选"
          className={style('candidateDismissLayer')}
          data-action-id="dismiss-candidates-in-workbench"
          role="button"
          onClick={onClose}
        />
      ) : null}
      <View className={classes(style('slotColumn'), style('slotColumnLeft'))}>
        {left.map((item) => <GearSlotRow key={item.slot} item={item} side="left" onClick={() => onSlot(item)} />)}
      </View>
      <View className={style('workbenchCenter')}>
        <View className={style('workbenchBackdrop')} data-role="gear-character-backdrop">
          <SystemGlyph assetId="quick-action-gear-glyph.default" className={style('centerCrest')} slotId="asset_slot.gear-workbench-crest" />
          <Text>{selectedSlot ? selectedSlotLabel : '点击左右槽位配置装备'}</Text>
        </View>
      </View>
      <View className={classes(style('slotColumn'), style('slotColumnRight'))}>
        {right.map((item) => <GearSlotRow key={item.slot} item={item} side="right" onClick={() => onSlot(item)} />)}
      </View>
      {candidateOpen && selectedSlot ? (
        <View className={style('candidatePanel')} data-slot-key={selectedSlot}>
          <View className={style('candidateHeading')}>
            <Text>{selectedSlotLabel}</Text>
            <View className={style('candidateHeadingActions')}>
              <Text data-role="gear-candidate-count">{candidateLoading ? '读取中' : `${candidates.length} 个候选`}</Text>
              <ControlButton
                aria-label="关闭装备候选"
                className={style('candidateClose')}
                data-action-id="close-candidates"
                onClick={onClose}
              >关闭</ControlButton>
            </View>
          </View>
          <ScrollView className={style('candidateScroll')} data-role="gear-candidate-scroll" enhanced scrollY showScrollbar={false}>
            <View className={style('candidateList')}>
              {notice ? (
                <View className={style('workbenchNotice')} data-role="gear-workbench-notice">
                  <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.gear-action-glyphs" />
                  <Text>{notice}</Text>
                </View>
              ) : null}
              {candidateLoading ? (
                Array.from({ length: 4 }, (_, index) => <View key={index} className={style('candidateSkeleton')} />)
              ) : candidates.length ? candidates.map((item) => (
                <ControlButton
                  key={item.id}
                  className={classes(style('candidateRow'), style(`candidateRow-${item.state}`))}
                  data-candidate-id={item.id}
                  data-role="gear-candidate-row"
                  data-state={item.state}
                  disabled={item.state === 'blocked'}
                  onClick={() => onCandidate(item)}
                >
                  <TrustedGearMedia className={style('candidateMedia')} iconUrl={item.iconUrl} label={item.label} />
                  <View className={style('candidateCopy')}>
                    <View className={style('candidateTitleRow')}>
                      <Text data-role="gear-candidate-title">{item.label}</Text>
                      {item.badgeLabels.length ? (
                        <View className={style('candidateBadges')} data-role="gear-candidate-badges">
                          {item.badgeLabels.slice(0, 2).map((label) => <Text key={label}>{label}</Text>)}
                        </View>
                      ) : null}
                    </View>
                    <Text data-role="gear-candidate-meta">{item.levelLabel} · {item.statSummary}</Text>
                    <Text data-role="gear-candidate-source">{item.sourceLabel}</Text>
                  </View>
                </ControlButton>
              )) : (
                <View className={style('emptyCenter')}>
                  <SystemGlyph assetId="quick-action-gear-glyph.default" className={style('centerCrest')} slotId="asset_slot.gear-workbench-crest" />
                  <Text>当前槽位没有可用候选</Text>
                </View>
              )}
              {enhancements.length ? (
                <View className={style('enhancementOptions')}>
                  <Text className={style('enhancementOptionsTitle')}>增强项</Text>
                  {enhancements.map((item) => (
                    <ControlButton
                      key={`${item.kind}-${item.id}`}
                      className={style('enhancementOption')}
                      data-active={item.selected ? 'true' : 'false'}
                      data-material-owner="css"
                      data-selection-material={item.selected ? 'active' : 'inactive'}
                      data-role="gear-enhancement-option"
                      onClick={() => onEnhancement(item)}
                    >
                      <TrustedGearMedia
                        className={style('enhancementOptionMedia')}
                        fallbackAssetId="utility-glyph-family.adjust"
                        iconUrl={item.iconUrl}
                        label={item.label}
                      />
                      <Text>{item.label}</Text>
                    </ControlButton>
                  ))}
                </View>
              ) : null}
            </View>
          </ScrollView>
        </View>
      ) : null}
      <ControlButton
        className={classes(style('primaryAction'), primaryDisabled && style('primaryActionDisabled'))}
        data-disabled={primaryDisabled ? 'true' : 'false'}
        data-role="gear-primary-action"
        disabled={primaryDisabled}
        onClick={onPrimary}
      >
        <SystemGlyph assetId="utility-glyph-family.runtime" slotId="asset_slot.gear-action-glyphs" />
        <Text>{primaryLabel}</Text>
      </ControlButton>
    </View>
  )
}

export interface GearActionItem {
  id: 'save' | 'import' | 'reset'
  label: string
  tone: 'gold' | 'blue' | 'metal'
  disabled?: boolean
  loading?: boolean
  onClick: () => void
}

const actionGlyph = {
  save: 'utility-glyph-family.save',
  import: 'utility-glyph-family.copy',
  reset: 'utility-glyph-family.reset',
} as const

export function GearActionRow({ items }: { items: readonly GearActionItem[] }) {
  return (
    <View className={style('actionsOwner')} data-owner="gear-action-row" data-region="secondary_actions_row">
      {items.map((item) => (
        <ControlButton
          key={item.id}
          className={classes(
            style('secondaryAction'),
            style(`secondaryAction-${item.tone}`),
            (item.disabled || item.loading) && style('secondaryActionDisabled'),
          )}
          data-action-id={item.id}
          data-disabled={item.disabled || item.loading ? 'true' : 'false'}
          data-role="gear-secondary-action"
          data-tone={item.tone}
          disabled={Boolean(item.disabled || item.loading)}
          onClick={item.onClick}
        >
          <SystemGlyph assetId={actionGlyph[item.id]} slotId="asset_slot.gear-action-glyphs" />
          <Text>{item.loading ? '处理中' : item.label}</Text>
        </ControlButton>
      ))}
    </View>
  )
}

export interface GearStatusItem {
  id: 'catalog' | 'selection' | 'validation' | 'evidence'
  label: string
  detail: string
  actionLabel?: string | undefined
  state: string
}

const statusGlyph = {
  catalog: 'utility-glyph-family.runtime',
  selection: 'quick-action-gear-glyph.default',
  validation: 'utility-glyph-family.warning',
  evidence: 'utility-glyph-family.document',
} as const

export interface GearStatusDeckProps {
  items: readonly GearStatusItem[]
  onAction: (item: GearStatusItem) => void
}

export function GearStatusDeck({ items, onAction }: GearStatusDeckProps) {
  return (
    <View className={style('statusOwner')} data-owner="gear-status-deck" data-region="status_footer_cards">
      {items.map((item) => (
        <View
          key={item.id}
          className={classes(style('statusCard'), style(`statusCard-${item.state}`))}
          data-role="gear-status-card"
          data-state={item.state}
          data-status-id={item.id}
          {...(item.actionLabel ? {
            'data-action-id': `status-${item.id}`,
            role: 'button',
            onClick: () => onAction(item),
          } : {})}
        >
          <View className={style('statusContent')}>
            <SystemGlyph assetId={statusGlyph[item.id]} className={style('statusGlyph')} slotId="asset_slot.gear-status-glyphs" />
            <Text className={style('statusLabel')}>{item.label}</Text>
            <Text className={style('statusDetail')}>{item.detail}</Text>
          </View>
          <Text className={style('statusAction')}>{item.actionLabel ?? '状态摘要'}</Text>
        </View>
      ))}
    </View>
  )
}
