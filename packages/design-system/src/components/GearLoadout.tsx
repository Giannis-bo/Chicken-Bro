import { Text, View } from '@tarojs/components'

import type { GearItemReference, GearSlotDefinition, ReadinessState, VerifiedWowObjectReference } from '@wow-mini/domain'
import { assetRuntimePath } from '@wow-mini/assets-manifest'

import { GameObjectIcon } from './GameObjectIcon'
import { StatusVisual } from './StatusVisual'
import { ownerClass, ownerStyle } from './style'

export interface GearLoadoutSlot extends GearSlotDefinition {
  item?: GearItemReference
  object?: VerifiedWowObjectReference
  state: ReadinessState
  stateLabel?: string
}

export interface GearLoadoutProps {
  slots: readonly GearLoadoutSlot[]
  selectedSlot?: string
  onSelect: (slot: GearLoadoutSlot) => void
}

function socketOptionCount(item: GearItemReference | undefined): number {
  return Array.isArray(item?.['socketOptions']) ? item['socketOptions'].length : 0
}

export function GearLoadout({ slots, selectedSlot, onSelect }: GearLoadoutProps) {
  const defaultFramePath = assetRuntimePath('item-socket-frame.default')
  const selectedFramePath = assetRuntimePath('item-socket-frame.selected')
  return (
    <View className={ownerStyle('gearGrid')}>
      {slots.map((slot) => {
        const socketCount = socketOptionCount(slot.item)
        return (
          <View
            key={slot.slot}
            className={ownerClass(ownerStyle('gearSlot'), slot.slot === selectedSlot && ownerStyle('gearSlotSelected'))}
            onClick={() => onSelect(slot)}
          >
            <View
              className={ownerStyle('gearIconFrame')}
              data-slot-id="slot-gear-slot-frame"
              {...(defaultFramePath ? { style: { backgroundImage: `url(${defaultFramePath})` } } : {})}
            >
              <GameObjectIcon fallbackLabel="空槽" object={slot.object} size={42} slotId="slot-gear-item-socket" />
            </View>
            <View>
              <Text className={ownerStyle('gearSlotLabel')}>{slot.label}</Text>
              <Text className={ownerStyle('gearItemName')}>{slot.item?.name ?? slot.item?.itemName ?? '未配置'}</Text>
              <StatusVisual compact label={slot.stateLabel} state={slot.state} />
              {socketCount > 0 ? (
                <View className={ownerStyle('gearSocketSummary')}>
                  <View
                    className={ownerStyle('gearSocket')}
                    data-slot-id="slot-enhancement-socket-generic"
                    {...(selectedFramePath ? { style: { backgroundImage: `url(${selectedFramePath})` } } : {})}
                  />
                  <Text>{socketCount} 个后端宝石候选</Text>
                </View>
              ) : null}
            </View>
          </View>
        )
      })}
    </View>
  )
}
