import { Text, View } from '@tarojs/components'

import { assetRuntimePath } from '@wow-mini/assets-manifest'
import type { ReadinessState, VerifiedWowObjectReference } from '@wow-mini/domain'

import { ActionButton } from './ActionButton'
import { GameObjectIcon } from './GameObjectIcon'
import { ProductionAssetImage } from './ProductionAsset'
import { ForgedPanel } from './ReconstructionPrimitives'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { WowPanel } from './WowPanel'
import { ownerStyle } from './style'
import { reconstructionStyle } from './reconstruction-style'

export interface WorkbenchModule {
  id: string
  title: string
  summary: string
  state: ReadinessState
  actionLabel: string
}

export interface WorkbenchCockpitProps {
  title: string
  subtitle?: string
  identity?: VerifiedWowObjectReference | null
  state: ReadinessState
  stateDetail?: string
  reasons?: readonly string[] | undefined
  showVerdictGlyph?: boolean | undefined
  modules?: readonly WorkbenchModule[] | undefined
  primaryAction?: { label: string; disabled?: boolean }
  onModule?: ((module: WorkbenchModule) => void) | undefined
  onPrimary?: () => void
  variant?: 'legacy' | 'blocker' | undefined
  showAssets?: boolean | undefined
}

export function WorkbenchCockpit({
  title,
  subtitle,
  identity,
  state,
  stateDetail,
  reasons = [],
  showVerdictGlyph = false,
  modules = [],
  primaryAction,
  onModule,
  onPrimary,
  variant = 'legacy',
  showAssets = true,
}: WorkbenchCockpitProps) {
  if (variant === 'blocker') {
    return (
      <ForgedPanel
        className={reconstructionStyle('workbenchBlocker')}
        contentInset={14}
        frameWidth={10}
        interactiveInset={14}
        owner="workbench-cockpit"
        region="current-spec-workbench_baseline_blocker-hero-card"
        tone="bright"
      >
        <View className={reconstructionStyle('workbenchBlockerCopy')} data-frame-content="true">
          <View className={reconstructionStyle('workbenchBlockerTitleRow')}>
            <SystemGlyph
              assetId="utility-glyph-family.warning"
              className={reconstructionStyle('workbenchBlockerLock')}
              slotId="asset_slot.utility-glyph-family"
            />
            <Text className={reconstructionStyle('workbenchBlockerEyebrow')}>{title}</Text>
          </View>
          <Text className={reconstructionStyle('workbenchBlockerHeadline')}>{stateDetail ?? '当前不可提交模拟'}</Text>
          <View className={reconstructionStyle('workbenchBlockerReasons')}>
            {(reasons.length ? reasons : [subtitle ?? '输入状态待读取', '证据状态待读取']).slice(0, 2).map((reason, index) => (
              <View key={`${index}-${reason}`} className={reconstructionStyle('workbenchBlockerReason')} data-role="workbench-blocker-reason">
                <View className={reconstructionStyle('workbenchBlockerReasonDot')} />
                <Text className={reconstructionStyle('workbenchBlockerReasonText')}>{reason}</Text>
              </View>
            ))}
          </View>
          {primaryAction ? (
            <ActionButton
              disabled={primaryAction.disabled}
              iconPath={assetRuntimePath('utility-glyph-family.chevron-right') ?? undefined}
              iconSlotId="asset_slot.utility-glyph-family"
              variant="primaryGold"
              onClick={onPrimary}
            >
              {primaryAction.label}
            </ActionButton>
          ) : null}
        </View>
        <View className={reconstructionStyle('workbenchBlockerEmblem')} data-frame-content="true">
          <ProductionAssetImage
            alt="阻断状态徽记"
            assetId="ornamental-emblem-family.blocker"
            enabled={showAssets}
            slotId="asset_slot.ornamental-emblem-family"
          />
          <SystemGlyph
            assetId="utility-glyph-family.warning"
            className={reconstructionStyle('workbenchBlockerWarning')}
            slotId="asset_slot.utility-glyph-family"
          />
        </View>
      </ForgedPanel>
    )
  }

  return (
    <WowPanel variant="cockpit">
      <View className={ownerStyle('cockpitHero')}>
        <GameObjectIcon fallbackLabel="专精" object={identity} size={58} slotId="slot-workbench-spec-icon" />
        <View>
          <Text className={ownerStyle('cockpitTitle')}>{title}</Text>
          {subtitle ? <Text className={ownerStyle('panelDescription')}>{subtitle}</Text> : null}
          <StatusVisual
            detail={stateDetail}
            glyph={showVerdictGlyph ? 'verdict' : undefined}
            state={state}
            variant="pill"
          />
        </View>
      </View>
      <View className={ownerStyle('cockpitModules')}>
        {modules.map((module) => (
          <View key={module.id} className={ownerStyle('cockpitModule')} onClick={() => onModule?.(module)}>
            <Text className={ownerStyle('cockpitModuleTitle')}>{module.title}</Text>
            <Text className={ownerStyle('cockpitModuleMeta')}>{module.summary}</Text>
            <StatusVisual compact glyph="module" state={module.state} variant="pill" />
            <ActionButton block variant="ghost" onClick={() => onModule?.(module)}>{module.actionLabel}</ActionButton>
          </View>
        ))}
      </View>
      {primaryAction ? (
        <ActionButton
          block
          disabled={primaryAction.disabled}
          variant="primaryGold"
          onClick={onPrimary}
        >
          {primaryAction.label}
        </ActionButton>
      ) : null}
    </WowPanel>
  )
}
