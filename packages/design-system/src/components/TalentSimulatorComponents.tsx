import { Image, Picker, ScrollView, Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'
import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'

import { isTrustedRuntimeMediaUrl } from '../runtime-media'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'
import styles from './TalentSimulatorComponents.module.scss'

function componentStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function componentClass(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

interface TrustedTalentMediaProps {
  iconUrl?: string | undefined
  label: string
  slotId: string
  fallbackGlyph?: string | undefined
  fallbackSlotId?: string | undefined
  className?: string | undefined
  dataRole?: string | undefined
  frameVariant?: 'plain' | 'shield' | undefined
}

function TrustedTalentMedia({
  iconUrl,
  label,
  slotId,
  fallbackGlyph = 'utility-glyph-family.topic',
  fallbackSlotId = 'asset_slot.utility-glyph-family',
  className,
  dataRole,
  frameVariant = 'plain',
}: TrustedTalentMediaProps) {
  const trustedUrl = isTrustedRuntimeMediaUrl(iconUrl) ? iconUrl ?? '' : ''
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setLoaded(false)
    setFailed(false)
  }, [trustedUrl])

  const visible = Boolean(trustedUrl) && loaded && !failed
  return (
    <View
      className={componentClass(
        componentStyle('trustedMedia'),
        frameVariant === 'shield' && componentStyle('trustedMediaShield'),
        className,
      )}
      data-role={dataRole}
      data-media-visible={visible ? 'true' : 'false'}
      data-frame-variant={frameVariant}
      data-slot-id={slotId}
    >
      <View
        className={componentStyle('trustedMediaInner')}
        data-role={dataRole ? `${dataRole}-object` : undefined}
      >
        <View className={componentStyle('trustedMediaFallback')}>
          <SystemGlyph assetId={fallbackGlyph} slotId={fallbackSlotId} />
        </View>
        {trustedUrl ? (
          <Image
            aria-label={label}
            className={componentClass(
              componentStyle('trustedMediaImage'),
              visible && componentStyle('trustedMediaImageVisible'),
            )}
            data-loaded={visible ? 'true' : 'false'}
            mode="aspectFill"
            src={trustedUrl}
            onError={() => setFailed(true)}
            onLoad={() => setLoaded(true)}
          />
        ) : null}
      </View>
    </View>
  )
}

export interface TalentSelectorOption {
  id: string
  label: string
}

export interface TalentSelectorItem {
  id: 'class' | 'spec' | 'hero'
  label: string
  value: string
  options: readonly TalentSelectorOption[]
  selectedIndex: number
  iconUrl?: string | undefined
  disabled?: boolean | undefined
}

export interface TalentSelectorPanelProps {
  items: readonly TalentSelectorItem[]
  loading?: boolean
  onSelect: (item: TalentSelectorItem, option: TalentSelectorOption) => void
}

const selectorGlyph: Readonly<Record<TalentSelectorItem['id'], string>> = {
  class: 'utility-glyph-family.shield',
  spec: 'utility-glyph-family.adjust',
  hero: 'quick-action-talents-glyph.default',
}

const selectorGlyphSlot: Readonly<Record<TalentSelectorItem['id'], string>> = {
  class: 'asset_slot.utility-glyph-family',
  spec: 'asset_slot.utility-glyph-family',
  hero: 'asset_slot.quick-action-talents-glyph',
}

export function TalentSelectorPanel({
  items,
  loading = false,
  onSelect,
}: TalentSelectorPanelProps) {
  return (
    <View
      className={componentStyle('selectorOwner')}
      data-owner="talent-selector-panel"
      data-region="selector_panel"
      data-slot-id="asset_slot.talent-selector-frame"
    >
      {items.map((item) => (
        <View key={item.id} className={componentStyle('selectorColumn')} data-selector-id={item.id}>
          <TrustedTalentMedia
            className={componentStyle('selectorCrest')}
            dataRole="talent-selector-crest"
            fallbackGlyph={selectorGlyph[item.id]}
            fallbackSlotId={selectorGlyphSlot[item.id]}
            frameVariant="shield"
            iconUrl={item.iconUrl}
            label={item.value}
            slotId="asset_slot.talent-selector-object"
          />
          <View className={componentStyle('selectorCopy')}>
            <Text className={componentStyle('selectorLabel')}>{item.label}</Text>
            {loading ? (
              <View className={componentStyle('selectorSkeleton')} />
            ) : (
              <Picker
                disabled={item.disabled || item.options.length < 2}
                mode="selector"
                range={item.options.map((option) => option.label)}
                value={item.selectedIndex}
                onChange={(event) => {
                  const option = item.options[Number(event.detail.value)]
                  if (option) onSelect(item, option)
                }}
              >
                <View
                  aria-label={`${item.label}：${item.value}`}
                  className={componentClass(
                    componentStyle('selectorValue'),
                    (item.disabled || item.options.length < 2) && componentStyle('selectorValueDisabled'),
                  )}
                  data-role="talent-selector-value"
                  data-disabled={item.disabled || item.options.length < 2 ? 'true' : 'false'}
                >
                  <Text>{item.value}</Text>
                  <View className={componentStyle('selectorChevron')} />
                </View>
              </Picker>
            )}
          </View>
        </View>
      ))}
    </View>
  )
}

export interface TalentTreeTabItem {
  id: string
  label: string
  disabled?: boolean
}

export interface TalentTreeTabsProps {
  items: readonly TalentTreeTabItem[]
  activeId: string
  loading?: boolean
  onSelect: (item: TalentTreeTabItem) => void
}

export function TalentTreeTabs({
  items,
  activeId,
  loading = false,
  onSelect,
}: TalentTreeTabsProps) {
  return (
    <View
      className={componentStyle('tabsOwner')}
      data-owner="talent-tree-tabs"
      data-slot-id="asset_slot.talent-tab-frame"
    >
      {items.map((item, index) => {
        const active = item.id === activeId
        return (
          <ControlButton
            key={item.id}
            className={componentClass(
              componentStyle('tab'),
              (loading || item.disabled === true) && componentStyle('tabDisabled'),
            )}
            data-active={active ? 'true' : 'false'}
            data-leading-boundary={active ? 'active' : index > 0 && items[index - 1]?.id === activeId ? 'suppressed' : 'inactive'}
            data-material-owner="css"
            data-selection-material={active ? 'active' : 'inactive'}
            data-role="talent-tree-tab"
            disabled={loading || item.disabled === true}
            onClick={() => onSelect(item)}
          >
            <Text>{item.label}</Text>
            {item.disabled ? (
              <SystemGlyph
                assetId="utility-glyph-family.warning"
                className={componentStyle('tabLock')}
                slotId="asset_slot.talent-readiness-glyphs"
              />
            ) : null}
          </ControlButton>
        )
      })}
    </View>
  )
}

export interface TalentPointSummaryProps {
  cap: number
  spent: number
  remaining: number
  loading?: boolean
}

export function TalentPointSummary({
  cap,
  spent,
  remaining,
  loading = false,
}: TalentPointSummaryProps) {
  const counters = [
    { id: 'cap', label: '可用点数', value: cap, tone: 'blue' },
    { id: 'spent', label: '已用点数', value: spent, tone: 'gold' },
    { id: 'remaining', label: '剩余点数', value: remaining, tone: 'green' },
  ] as const
  return (
    <View className={componentStyle('pointsOwner')} data-owner="talent-point-summary" data-region="points_summary_bar">
      {counters.map((counter) => (
        <View key={counter.id} className={componentStyle('pointCounter')} data-counter-id={counter.id}>
          <Text>{counter.label}</Text>
          <View
            className={componentClass(componentStyle('pointBadge'), componentStyle(`pointBadge-${counter.tone}`))}
            data-role="talent-point-badge"
            data-tone={counter.tone}
          >
            <Text data-role={`talent-point-${counter.id}`}>{loading ? '--' : counter.value}</Text>
          </View>
        </View>
      ))}
      <SystemGlyph
        assetId="source-badge-family.information"
        className={componentStyle('pointsInfo')}
        slotId="asset_slot.talent-readiness-glyphs"
      />
    </View>
  )
}

export interface TalentGraphNodeItem {
  id: string
  label: string
  description: string
  descriptionStatus: string
  x: number
  y: number
  row: number
  column: number
  rank: number
  maxRank: number
  iconUrl?: string | undefined
  shape: string
  choiceOptionIds: readonly string[]
  granted: boolean
  state: 'selected' | 'available' | 'unselected' | 'blocked' | 'loading'
  loading: boolean
}

export interface TalentGraphEdgeItem {
  id: string
  x: number
  y: number
  width: number
  angle: number
  state: 'selected' | 'available' | 'blocked' | 'loading'
}

interface TalentGraphNodeProps {
  node: TalentGraphNodeItem
  readonly: boolean
  onNode: (node: TalentGraphNodeItem) => void
}

function TalentGraphNode({ node, readonly, onNode }: TalentGraphNodeProps) {
  const nodeStyle = {
    left: `${node.x}rpx`,
    top: `${node.y}rpx`,
  } as CSSProperties
  return (
    <View
      aria-label={node.loading
        ? '天赋节点读取中'
        : `${node.label}，${node.rank}/${node.maxRank}${node.choiceOptionIds.length > 1 ? `，${node.choiceOptionIds.length}选1` : ''}`}
      className={componentClass(
        componentStyle('graphNode'),
        componentStyle(`graphNode-${node.state}`),
        node.shape === 'choice' && componentStyle('graphNodeChoice'),
        node.granted && componentStyle('graphNodeGranted'),
      )}
      data-granted={node.granted ? 'true' : 'false'}
      data-node-column={node.column}
      data-node-id={node.id}
      data-node-row={node.row}
      data-shape={node.shape}
      data-state={node.state}
      data-disabled={readonly || node.state === 'blocked' || node.loading ? 'true' : 'false'}
      role="button"
      style={nodeStyle}
      onClick={() => {
        if (!readonly && node.state !== 'blocked' && !node.loading) onNode(node)
      }}
    >
      {node.loading ? <View className={componentStyle('nodeSkeleton')} /> : (
        <>
          {node.shape === 'choice' ? (
            <View className={componentStyle('choiceFrame')} data-role="talent-choice-frame" />
          ) : null}
          <TrustedTalentMedia
            className={componentClass(componentStyle('nodeMedia'), node.loading && componentStyle('nodeMediaLoading'))}
            iconUrl={node.iconUrl}
            label={node.label}
            slotId="asset_slot.talent-node-object"
          />
          <Text className={componentStyle('nodeFallbackLabel')}>{node.label.slice(0, 1)}</Text>
          <Text className={componentStyle('nodeRank')}>{node.rank}/{node.maxRank}</Text>
        </>
      )}
    </View>
  )
}

export interface TalentGraphViewportProps {
  nodes: readonly TalentGraphNodeItem[]
  edges: readonly TalentGraphEdgeItem[]
  connectivityStatus: 'loading' | 'ready' | 'unavailable'
  planeWidth: number
  planeHeight: number
  nodeCount: number
  uniquePositionCount: number
  readonly?: boolean
  onNode: (node: TalentGraphNodeItem) => void
}

const graphViewportHeight = 628

export function TalentGraphViewport({
  nodes,
  edges,
  connectivityStatus,
  planeWidth,
  planeHeight,
  nodeCount,
  uniquePositionCount,
  readonly = false,
  onNode,
}: TalentGraphViewportProps) {
  const loading = nodes.every((node) => node.loading)
  const minNodeX = nodes.length ? Math.min(...nodes.map((node) => node.x)) : 0
  const minNodeY = nodes.length ? Math.min(...nodes.map((node) => node.y)) : 0
  const maxNodeX = nodes.length ? Math.max(...nodes.map((node) => node.x)) : planeWidth
  const maxNodeY = nodes.length ? Math.max(...nodes.map((node) => node.y)) : planeHeight
  const nodeBoundsWidth = Math.max(1, maxNodeX - minNodeX)
  const nodeBoundsHeight = Math.max(1, maxNodeY - minNodeY)
  const stageWidth = planeWidth
  const stageHeight = planeHeight
  const stageStyle = {
    width: `${stageWidth}rpx`,
    height: `${stageHeight}rpx`,
  } as CSSProperties
  const planeStyle = {
    width: `${planeWidth}rpx`,
    height: `${planeHeight}rpx`,
    left: '0rpx',
    top: '0rpx',
  } as CSSProperties
  return (
    <View
      className={componentClass(componentStyle('graphOwner'), loading && componentStyle('graphOwnerLoading'))}
      data-edge-count={edges.length}
      data-connectivity-status={connectivityStatus}
      data-loading={loading ? 'true' : 'false'}
      data-node-count={nodeCount}
      data-node-bounds-height={nodeBoundsHeight}
      data-node-bounds-width={nodeBoundsWidth}
      data-owner="talent-graph-viewport"
      data-plane-width={planeWidth}
      data-region="tree_canvas"
      data-slot-id="asset_slot.talent-node-shell"
      data-stage-height={stageHeight}
      data-stage-width={stageWidth}
      data-unique-position-count={uniquePositionCount}
    >
      {connectivityStatus === 'unavailable' ? (
        <View className={componentStyle('connectivityNotice')} data-role="talent-connectivity-notice">
          <SystemGlyph assetId="utility-glyph-family.warning" slotId="asset_slot.talent-readiness-glyphs" />
          <Text>连接规则待核验 · 当前只读</Text>
        </View>
      ) : null}
      <ScrollView
        className={componentStyle('graphScroll')}
        scrollLeft={0}
        scrollTop={0}
        scrollX={false}
        scrollY={stageHeight > graphViewportHeight}
        showScrollbar={false}
      >
        <View className={componentStyle('graphStage')} style={stageStyle}>
          <View className={componentStyle('graphPlane')} style={planeStyle}>
            <View className={componentStyle('graphEtching')} data-role="talent-graph-etching" />
            {edges.map((edge) => (
              <View
                key={edge.id}
                className={componentClass(componentStyle('graphEdge'), componentStyle(`graphEdge-${edge.state}`))}
                data-arrow="end"
                data-edge-id={edge.id}
                data-state={edge.state}
                style={{
                  left: `${edge.x}rpx`,
                  top: `${edge.y}rpx`,
                  width: `${edge.width}rpx`,
                  transform: `rotate(${edge.angle}deg)`,
                }}
              />
            ))}
            {nodes.map((node) => (
              <TalentGraphNode key={node.id} node={node} readonly={readonly} onNode={onNode} />
            ))}
          </View>
        </View>
      </ScrollView>
    </View>
  )
}

export function TalentLegend() {
  const items = [
    { id: 'selected', label: '已点亮' },
    { id: 'available', label: '可提升' },
    { id: 'unselected', label: '未点亮' },
    { id: 'blocked', label: '不可用' },
  ] as const
  return (
    <View className={componentStyle('legendOwner')} data-owner="talent-legend" data-region="legend_bar">
      {items.map((item) => (
        <View
          key={item.id}
          className={componentClass(componentStyle('legendItem'), componentStyle(`legendItem-${item.id}`))}
          data-state={item.id}
        >
          <View className={componentStyle('legendSocket')} data-role="talent-legend-socket">
            {item.id === 'blocked' ? (
              <SystemGlyph assetId="utility-glyph-family.warning" slotId="asset_slot.talent-readiness-glyphs" />
            ) : null}
          </View>
          <Text>{item.label}</Text>
        </View>
      ))}
    </View>
  )
}

export interface TalentImportStatusItem {
  id: string
  label: string
  state: 'ready' | 'partial' | 'blocked'
}

export interface TalentImportStatusProps {
  title: string
  headline: string
  detail: string
  statuses: readonly TalentImportStatusItem[]
  loading?: boolean | undefined
  onOpen?: (() => void) | undefined
}

const importStatusGlyph: Readonly<Record<TalentImportStatusItem['state'], string>> = {
  ready: 'status-dot-family.ready',
  partial: 'status-dot-family.running',
  blocked: 'status-dot-family.error',
}

export function TalentImportStatus({
  title,
  headline,
  detail,
  statuses,
  loading = false,
  onOpen,
}: TalentImportStatusProps) {
  return (
    <View
      className={componentStyle('importOwner')}
      data-owner="talent-import-status"
      data-region="websim_panel"
      data-slot-id="asset_slot.talent-selector-frame"
    >
      <View className={componentStyle('importMain')} {...(onOpen ? { onClick: onOpen } : {})}>
        <View className={componentStyle('importTitle')}>
          <View className={componentStyle('importTitleMedallion')} data-role="talent-import-globe-medallion">
            <SystemGlyph
              assetId="utility-glyph-family.globe"
              className={componentStyle('importTitleGlyph')}
              slotId="asset_slot.talent-readiness-glyphs"
            />
          </View>
          <Text>{title}</Text>
        </View>
        <View className={componentStyle('importPrompt')} data-role="talent-import-prompt">
          <View className={componentStyle('importUploadMedallion')} data-role="talent-import-upload-medallion">
            <SystemGlyph
              assetId="utility-glyph-family.cloud-upload"
              className={componentStyle('importUploadGlyph')}
              slotId="asset_slot.talent-readiness-glyphs"
            />
          </View>
          <View className={componentStyle('importPromptCopy')}>
            <Text>{loading ? '读取构筑状态' : headline}</Text>
            <Text>{loading ? '正在核对后端天赋证据' : detail}</Text>
          </View>
        </View>
      </View>
      <View className={componentStyle('importStatuses')}>
        {statuses.map((status) => (
          <View
            key={status.id}
            className={componentClass(componentStyle('importStatusRow'), componentStyle(`importStatusRow-${status.state}`))}
            data-state={status.state}
          >
            <View className={componentStyle('importStatusMarker')} />
            <Text>{loading ? '读取中' : status.label}</Text>
            <SystemGlyph
              assetId={importStatusGlyph[status.state]}
              className={componentStyle('importStatusGlyph')}
              slotId="asset_slot.talent-readiness-glyphs"
            />
          </View>
        ))}
      </View>
    </View>
  )
}

export interface TalentCommunityRowProps {
  title: string
  detail: string
  disabled?: boolean
  onClick: () => void
}

export function TalentCommunityRow({
  title,
  detail,
  disabled = false,
  onClick,
}: TalentCommunityRowProps) {
  return (
    <View
      className={componentClass(componentStyle('communityOwner'), disabled && componentStyle('communityOwnerDisabled'))}
      data-disabled={disabled ? 'true' : 'false'}
      data-owner="talent-community-row"
      data-region="community_template_row"
      role="button"
      onClick={() => {
        if (!disabled) onClick()
      }}
    >
      <SystemGlyph
        assetId="utility-glyph-family.user"
        className={componentStyle('communityGlyph')}
        slotId="asset_slot.talent-community-row"
      />
      <Text className={componentStyle('communityTitle')}>{title}</Text>
      <Text className={componentStyle('communityDetail')}>{detail}</Text>
      <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.talent-community-row" />
    </View>
  )
}

export interface TalentActionItem {
  id: 'save' | 'import' | 'reset'
  label: string
  disabled?: boolean | undefined
  tone: 'gold' | 'blue' | 'metal'
  onClick: () => void
}

const actionGlyph: Readonly<Record<TalentActionItem['id'], string>> = {
  save: 'utility-glyph-family.save',
  import: 'utility-glyph-family.copy',
  reset: 'utility-glyph-family.reset',
}

export interface TalentActionBarProps {
  items: readonly TalentActionItem[]
}

export function TalentActionBar({ items }: TalentActionBarProps) {
  return (
    <View
      className={componentStyle('actionsOwner')}
      data-owner="talent-action-bar"
      data-region="bottom_action_bar"
      data-slot-id="asset_slot.talent-action-frame"
    >
      {items.map((item) => (
        <View
          key={item.id}
          className={componentClass(
            componentStyle('actionButton'),
            componentStyle(`actionButton-${item.tone}`),
            item.disabled === true && componentStyle('actionButtonDisabled'),
          )}
          data-action-id={item.id}
          data-disabled={item.disabled === true ? 'true' : 'false'}
          data-role="talent-action-button"
          data-tone={item.tone}
          role="button"
          onClick={() => {
            if (item.disabled !== true) item.onClick()
          }}
        >
          <SystemGlyph assetId={actionGlyph[item.id]} slotId="asset_slot.utility-glyph-family" />
          <Text>{item.label}</Text>
        </View>
      ))}
    </View>
  )
}
