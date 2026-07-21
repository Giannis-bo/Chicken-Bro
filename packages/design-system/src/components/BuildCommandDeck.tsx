import { Text, View } from '@tarojs/components'

import type { ProductionAssetId } from '@wow-mini/assets-manifest'

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

function componentStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

export function BuildCommandDeck(props: {
  items: readonly BuildCommandDeckItem[]
  loading?: boolean
  onSelect: (id: BuildCommandDeckItem['id']) => void
}): JSX.Element {
  const { items, loading = false, onSelect } = props

  return (
    <View className={componentStyle('commandDeck')} data-owner="build-command-deck">
      {items.map((item) => {
        const interactionDisabled = loading || item.disabled
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
              onClick={() => onSelect(item.id)}
            >
              <View className={componentStyle('commandCardMedallion')}>
                <ProductionAssetGlyph
                  assetId={item.glyphAssetId}
                  className={componentStyle('commandCardGlyph')}
                  dataRole={'build-command-' + item.id + '-glyph'}
                  fallbackAssetId={item.fallbackGlyphAssetId}
                  fallbackSlotId="asset_slot.utility-glyph-family"
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
