import { Image, Text, View } from '@tarojs/components'
import type { ReactNode } from 'react'

import { assetRuntimePath, type ProductionAssetId } from '@wow-mini/assets-manifest'

import { NineSliceFrame } from './NineSliceFrame'
import { ownerClass, ownerStyle } from './style'

export type ActionButtonVariant = 'primaryGold' | 'secondaryMetal' | 'secondaryArcane' | 'ghost' | 'danger'

export interface ActionButtonProps {
  children?: ReactNode | undefined
  className?: string | undefined
  variant?: ActionButtonVariant | undefined
  iconPath?: string | undefined
  iconSlotId?: string | undefined
  iconDirection?: 'default' | 'back' | undefined
  disabled?: boolean | undefined
  loading?: boolean | undefined
  block?: boolean | undefined
  ariaLabel?: string | undefined
  dataActionId?: string | undefined
  dataRole?: string | undefined
  dataState?: string | undefined
  onClick?: (() => void) | undefined
}

const variantClass: Readonly<Record<ActionButtonVariant, string>> = {
  primaryGold: ownerStyle('buttonPrimary'),
  secondaryMetal: '',
  secondaryArcane: ownerStyle('buttonArcane'),
  ghost: ownerStyle('buttonGhost'),
  danger: ownerStyle('buttonDanger'),
}

const materialByVariant: Partial<Record<ActionButtonVariant, ProductionAssetId>> = {
  primaryGold: 'action-material-family.gold-default',
  secondaryMetal: 'action-material-family.secondary-outline',
}

export function ActionButton({
  children,
  className,
  variant = 'secondaryMetal',
  iconPath,
  iconSlotId,
  iconDirection = 'default',
  disabled = false,
  loading = false,
  block = false,
  ariaLabel,
  dataActionId,
  dataRole,
  dataState,
  onClick,
}: ActionButtonProps) {
  const iconOnly = children === null || children === undefined
  const content = typeof children === 'string' || typeof children === 'number'
    ? <Text>{children}</Text>
    : children
  const materialAssetId = disabled && variant === 'primaryGold'
    ? 'action-material-family.gold-disabled'
    : materialByVariant[variant]
  const materialAssetReady = materialAssetId ? Boolean(assetRuntimePath(materialAssetId)) : false

  return (
    <View
      className={ownerClass(
        ownerStyle('button'),
        variantClass[variant],
        block && ownerStyle('buttonBlock'),
        iconOnly && ownerStyle('buttonIconOnly'),
        materialAssetReady && ownerStyle('buttonMaterial'),
        disabled && ownerStyle('buttonDisabled'),
        className,
      )}
      aria-disabled={disabled || loading ? 'true' : undefined}
      data-action-id={dataActionId}
      data-disabled={disabled || loading ? 'true' : 'false'}
      data-loading={loading ? 'true' : 'false'}
      data-material-owner={materialAssetReady ? 'asset' : 'css'}
      data-role={dataRole}
      data-state={dataState}
      hoverClass={ownerStyle('buttonPressed')}
      hoverStayTime={80}
      role="button"
      {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
      {...(onClick ? { onClick: () => { if (!disabled && !loading) onClick() } } : {})}
    >
      {materialAssetId && materialAssetReady ? (
        <NineSliceFrame
          assetId={materialAssetId}
          frameWidth={10}
          scope="control"
          slotId="asset_slot.action-material-family"
        />
      ) : null}
      {iconPath ? (
        <Image
          className={ownerClass(ownerStyle('buttonIcon'), iconDirection === 'back' && ownerStyle('buttonIconBack'))}
          mode="aspectFit"
          src={iconPath}
          {...(iconSlotId ? { 'data-slot-id': iconSlotId } : {})}
        />
      ) : null}
      {iconOnly ? null : content}
    </View>
  )
}
