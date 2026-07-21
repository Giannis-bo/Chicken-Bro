import { Image, Text, View } from '@tarojs/components'
import { useState } from 'react'

import { resolveRuntimeMediaUrl } from '../runtime-media'
import { ControlButton } from './ControlButton'
import { ForgedPanel } from './ReconstructionPrimitives'
import { styleSelectorClass } from './selector-markers'
import styles from './BuildsHomeCommandDeck.module.scss'

export interface BuildClassSelectorOption {
  id: string
  label: string
  iconUrl?: string
  disabled: boolean
  selected: boolean
}

export interface BuildClassSelectorProps {
  options: readonly BuildClassSelectorOption[]
  disabled?: boolean
  value: string
  onSelect: (id: string) => void
}

interface ClassIconProps {
  failedIconUrls: readonly string[]
  label: string
  iconUrl?: string | undefined
  onError: (iconUrl: string) => void
}

function componentStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function classInitial(label: string): string {
  return label.trim().slice(0, 1) || '?'
}

function ClassIcon({ failedIconUrls, label, iconUrl, onError }: ClassIconProps) {
  const resolvedIconUrl = resolveRuntimeMediaUrl(iconUrl)
  const showIcon = Boolean(resolvedIconUrl) && !failedIconUrls.includes(resolvedIconUrl)

  return (
    <View className={componentStyle('classIcon')} aria-hidden>
      <Text className={componentStyle('classIconFallback')}>{classInitial(label)}</Text>
      {showIcon ? (
        <Image
          className={componentStyle('classIconImage')}
          mode="aspectFill"
          src={resolvedIconUrl}
          onError={() => onError(resolvedIconUrl)}
        />
      ) : null}
    </View>
  )
}

export function BuildClassSelector({
  options,
  disabled = false,
  value,
  onSelect,
}: BuildClassSelectorProps): JSX.Element {
  const [open, setOpen] = useState(false)
  const [failedIconUrls, setFailedIconUrls] = useState<readonly string[]>([])
  const selectedId = options.some((option) => option.id === value)
    ? value
    : options.find((option) => option.selected)?.id
  const selectedOption = options.find((option) => option.id === selectedId)
  const selectorDisabled = disabled || options.length === 0
  const selectedLabel = selectedOption?.label ?? '选择职业'

  const rememberIconFailure = (iconUrl: string) => {
    setFailedIconUrls((current) => current.includes(iconUrl) ? current : [...current, iconUrl])
  }

  const selectOption = (option: BuildClassSelectorOption) => {
    if (disabled || option.disabled) return
    onSelect(option.id)
    setOpen(false)
  }

  return (
    <View
      className={componentStyle('classSelectorOwner')}
      data-owner="build-class-selector"
    >
      <ControlButton
        aria-label={'选择职业，当前为' + selectedLabel}
        className={componentStyle('classSelectorTrigger')}
        data-disabled={selectorDisabled ? 'true' : 'false'}
        data-role="build-class-selector"
        disabled={selectorDisabled}
        onClick={() => setOpen(true)}
      >
        <ClassIcon
          failedIconUrls={failedIconUrls}
          iconUrl={selectedOption?.iconUrl}
          label={selectedLabel}
          onError={rememberIconFailure}
        />
        <Text className={componentStyle('classSelectorLabel')}>{selectedLabel}</Text>
        <View className={componentStyle('classSelectorCaret')} aria-hidden />
      </ControlButton>

      {open ? (
        <>
          <View
            aria-label="关闭职业选择"
            className={componentStyle('classSelectorScrim')}
            role="button"
            onClick={() => setOpen(false)}
          />
          <View className={componentStyle('classSelectorSheet')} data-owner="build-class-selector-sheet">
            <ForgedPanel
              className={componentStyle('classSelectorPanel')}
              contentInset={4}
              frameWidth={8}
              interactiveInset={6}
              owner="build-class-selector"
              region="class_selector_panel"
              tone="raised"
            >
              <View className={componentStyle('classSelectorPanelContent')} data-frame-content="true">
                <View className={componentStyle('classSelectorPanelHeader')}>
                  <Text className={componentStyle('classSelectorPanelTitle')}>选择职业</Text>
                  <ControlButton
                    aria-label="取消职业选择"
                    className={componentStyle('classSelectorCancel')}
                    data-action-id="cancel-build-class-selection"
                    onClick={() => setOpen(false)}
                  >
                    取消
                  </ControlButton>
                </View>
                <View className={componentStyle('classSelectorGrid')}>
                  {options.map((option) => {
                    const optionDisabled = disabled || option.disabled
                    const optionSelected = option.id === selectedId
                    return (
                      <ControlButton
                        key={option.id}
                        aria-label={option.label}
                        className={componentStyle('classSelectorOption')}
                        data-disabled={optionDisabled ? 'true' : 'false'}
                        data-material-owner="css"
                        data-option-id={option.id}
                        data-role="build-class-option"
                        data-selection-material={optionSelected ? 'active' : 'inactive'}
                        data-selected={optionSelected ? 'true' : 'false'}
                        disabled={optionDisabled}
                        onClick={() => selectOption(option)}
                      >
                        <ClassIcon
                          failedIconUrls={failedIconUrls}
                          iconUrl={option.iconUrl}
                          label={option.label}
                          onError={rememberIconFailure}
                        />
                        <Text className={componentStyle('classSelectorOptionLabel')}>{option.label}</Text>
                      </ControlButton>
                    )
                  })}
                </View>
              </View>
            </ForgedPanel>
          </View>
        </>
      ) : null}
    </View>
  )
}
