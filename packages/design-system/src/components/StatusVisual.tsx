import { Text, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import type { ReadinessState } from '@wow-mini/domain'

import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { SystemGlyph } from './SystemGlyph'
import { dataSelectorClass } from './selector-markers'
import { ownerClass, ownerStyle } from './style'

const stateLabel: Readonly<Record<ReadinessState, string>> = {
  loading: '加载中', empty: '暂无内容', error: '请求失败', blocked: '已阻断', partial: '部分可用',
  ready: '已就绪', stale: '数据已过期', source_reference: '来源参考', unknown: '状态未知',
}

const stateColor: Readonly<Record<ReadinessState, string>> = {
  loading: 'var(--wow-status-stale)', empty: 'var(--wow-status-unknown)', error: 'var(--wow-status-blocked)',
  blocked: 'var(--wow-status-blocked)', partial: 'var(--wow-status-partial)', ready: 'var(--wow-status-ready)',
  stale: 'var(--wow-status-stale)', source_reference: 'var(--wow-status-source)', unknown: 'var(--wow-status-unknown)',
}

export interface StatusVisualProps {
  state: ReadinessState
  label?: string | undefined
  detail?: string | undefined
  compact?: boolean | undefined
  glyph?: 'verdict' | 'row' | 'module' | undefined
  variant?: 'inline' | 'pill' | undefined
  tone?: 'semantic' | 'evidence' | undefined
}

const statusAsset = {
  loading: { assetId: 'status-dot-family.running', slotId: 'asset_slot.status-dot-family' },
  empty: { assetId: 'status-dot-family.reference', slotId: 'asset_slot.status-dot-family' },
  error: { assetId: 'status-dot-family.error', slotId: 'asset_slot.status-dot-family' },
  blocked: { assetId: 'status-dot-family.error', slotId: 'asset_slot.status-dot-family' },
  partial: { assetId: 'status-pill-family.partial', slotId: 'asset_slot.status-pill-family' },
  ready: { assetId: 'status-dot-family.ready', slotId: 'asset_slot.status-dot-family' },
  stale: { assetId: 'status-dot-family.reference', slotId: 'asset_slot.status-dot-family' },
  source_reference: { assetId: 'status-dot-family.reference', slotId: 'asset_slot.status-dot-family' },
  unknown: { assetId: 'status-pill-family.partial', slotId: 'asset_slot.status-pill-family' },
} as const

const evidenceAsset: Readonly<Record<ReadinessState, string>> = {
  loading: 'news-evidence-glyph.fallback',
  empty: 'news-evidence-glyph.unavailable',
  error: 'news-evidence-glyph.unavailable',
  blocked: 'news-evidence-glyph.unavailable',
  partial: 'news-evidence-glyph.fallback',
  ready: 'news-evidence-glyph.verified',
  stale: 'news-evidence-glyph.fallback',
  source_reference: 'news-evidence-glyph.source',
  unknown: 'news-evidence-glyph.unavailable',
}

export function StatusVisual({
  state,
  label,
  detail,
  compact = false,
  glyph,
  variant = 'inline',
  tone = 'semantic',
}: StatusVisualProps) {
  const style = {
    '--status-color': tone === 'evidence' ? 'var(--wow-status-evidence)' : stateColor[state],
  } as CSSProperties
  const glyphAsset = glyph ? statusAsset[state] : undefined
  return (
    <View className={ownerStyle('statusBlock')}>
      <View
        className={ownerClass(
          ownerStyle('status'),
          variant === 'pill' && ownerStyle('statusPill'),
          dataSelectorClass('status-state', state),
        )}
        data-status-state={state}
        data-status-tone={tone}
        style={style}
      >
        {glyphAsset ? (
          tone === 'evidence' ? (
            <ProductionAssetGlyph
              assetId={evidenceAsset[state]}
              className={ownerStyle('statusGlyph')}
              fallbackAssetId={glyphAsset.assetId}
              fallbackSlotId={glyphAsset.slotId}
              slotId="asset_slot.news-evidence-glyph"
            />
          ) : (
            <SystemGlyph
              assetId={glyphAsset.assetId}
              className={ownerStyle('statusGlyph')}
              slotId={glyphAsset.slotId}
            />
          )
        ) : <View className={ownerStyle('statusDot')} />}
        <Text className={ownerStyle('statusLabel')}>{label ?? stateLabel[state]}</Text>
      </View>
      {detail && !compact ? <Text className={ownerStyle('statusDetail')}>{detail}</Text> : null}
    </View>
  )
}
