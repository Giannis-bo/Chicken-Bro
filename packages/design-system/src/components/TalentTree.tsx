import { Text, View } from '@tarojs/components'
import type { CSSProperties } from 'react'

import type { ReadinessState } from '@wow-mini/domain'
import { assetRuntimePath } from '@wow-mini/assets-manifest'

import { ownerClass, ownerStyle } from './style'

export interface TalentTreeNodeView {
  id: string
  label: string
  row: number
  column: number
  rank: number
  maxRank: number
  state: Extract<ReadinessState, 'ready' | 'partial' | 'blocked' | 'unknown'>
}

export interface TalentTreeProps {
  nodes: readonly TalentTreeNodeView[]
  spentPoints: number
  maxPoints: number
  columns?: number
  readonly?: boolean
  onNode: (node: TalentTreeNodeView) => void
}

export function TalentTree({
  nodes,
  spentPoints,
  maxPoints,
  columns = 7,
  readonly = false,
  onNode,
}: TalentTreeProps) {
  const gridStyle = { '--talent-columns': columns } as CSSProperties
  const talentMaterialPath = assetRuntimePath('talent-tree-grid.arcane-grid')
  const canvasStyle = talentMaterialPath
    ? ({ '--talent-material': `url(${talentMaterialPath})` } as CSSProperties)
    : undefined
  return (
    <View
      className={ownerStyle('talentCanvas')}
      data-slot-id="asset_slot.talent-tree-grid"
      {...(canvasStyle ? { style: canvasStyle } : {})}
    >
      <View className={ownerStyle('talentPoints')}>
        <Text>已用点数 {spentPoints}</Text>
        <Text>上限 {maxPoints}</Text>
      </View>
      <View className={ownerStyle('talentGrid')} style={gridStyle}>
        {nodes.map((node) => (
          <View
            key={node.id}
            className={ownerClass(
              ownerStyle('talentNode'),
              node.rank > 0 && ownerStyle('talentNodeSelected'),
              node.state === 'blocked' && ownerStyle('talentNodeBlocked'),
            )}
            style={{ gridColumn: node.column, gridRow: node.row }}
            onClick={() => {
              if (!readonly && node.state !== 'blocked') onNode(node)
            }}
          >
            <Text>{node.label}</Text>
            <Text>{node.rank}/{node.maxRank}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}
