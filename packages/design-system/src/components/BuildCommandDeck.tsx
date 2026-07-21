import { Text, View } from '@tarojs/components'

import {
  candidateAssets,
  productionAssets,
  type AssetSlotId,
  type ProductionAssetId,
} from '@wow-mini/assets-manifest'

import { ControlButton } from './ControlButton'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ForgedPanel } from './ReconstructionPrimitives'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'
import styles from './BuildsHomeCommandDeck.module.scss'

export interface BuildCommandDeckItem {
  id: 'talents' | 'gear' | 'simc' | 'tasks'
  title: string
  detail: string
  glyphAssetId: ProductionAssetId
  fallbackGlyphAssetId: ProductionAssetId
  disabled: boolean
}

export interface BuildCommandDeckEntry {
  item: BuildCommandDeckItem
  interactionDisabled: boolean
  fallbackGlyphSlotId: AssetSlotId
}

function componentStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function registeredAssetSlotId(assetId: ProductionAssetId): AssetSlotId {
  return productionAssets.find((asset) => asset.assetId === assetId)?.slotId
    ?? candidateAssets.find((asset) => asset.assetId === assetId)?.slotId
    ?? 'asset_slot.unregistered-fallback'
}

export function buildCommandDeckEntries(
  items: readonly BuildCommandDeckItem[],
  loading = false,
): readonly BuildCommandDeckEntry[] {
  return items.map((item) => ({
    item,
    interactionDisabled: loading || item.disabled,
    fallbackGlyphSlotId: registeredAssetSlotId(item.fallbackGlyphAssetId),
  }))
}

export function activateBuildCommand(
  entry: Pick<BuildCommandDeckEntry, 'item' | 'interactionDisabled'>,
  onSelect: (id: BuildCommandDeckItem['id']) => void,
): boolean {
  if (entry.interactionDisabled) return false
  onSelect(entry.item.id)
  return true
}

export function BuildCommandDeck(props: {
  items: readonly BuildCommandDeckItem[]
  loading?: boolean
  onSelect: (id: BuildCommandDeckItem['id']) => void
}): JSX.Element {
  const { items, loading = false, onSelect } = props

  return (
    <View className={componentStyle('commandDeck')} data-owner="build-command-deck">
      {buildCommandDeckEntries(items, loading).map((entry) => {
        const { item, interactionDisabled, fallbackGlyphSlotId } = entry
        return (
          <ForgedPanel
            key={item.id}
            className={componentStyle('commandCardFrame')}
            contentInset={3}
            frameWidth={8}
            interactiveInset={5}
            owner="build-command-deck"
            region={'command_card_' + item.id}
            tone="inset"
          >
            <ControlButton
              aria-label={[item.title, item.detail].join('，')}
              className={componentStyle('commandCard')}
              data-command-id={item.id}
              data-disabled={interactionDisabled ? 'true' : 'false'}
              data-frame-content="true"
              data-material-owner="css"
              data-role="build-command-card"
              disabled={interactionDisabled}
              onClick={() => activateBuildCommand(entry, onSelect)}
            >
              <View className={componentStyle('commandCardMedallion')}>
                <ProductionAssetGlyph
                  assetId={item.glyphAssetId}
                  className={componentStyle('commandCardGlyph')}
                  dataRole={'build-command-' + item.id + '-glyph'}
                  fallbackAssetId={item.fallbackGlyphAssetId}
                  fallbackSlotId={fallbackGlyphSlotId}
                  slotId="asset_slot.builds-evidence-medallions"
                />
              </View>
              <View className={componentStyle('commandCardCopy')}>
                <Text className={componentStyle('commandCardTitle')}>{item.title}</Text>
                <Text className={componentStyle('commandCardDetail')}>{item.detail}</Text>
              </View>
              <View className={componentStyle('commandCardChevron')}>
                <SystemGlyph
                  assetId="utility-glyph-family.chevron-right"
                  className={componentStyle('commandCardChevronGlyph')}
                  dataRole="build-command-chevron"
                  slotId="asset_slot.utility-glyph-family"
                />
              </View>
            </ControlButton>
          </ForgedPanel>
        )
      })}
    </View>
  )
}
