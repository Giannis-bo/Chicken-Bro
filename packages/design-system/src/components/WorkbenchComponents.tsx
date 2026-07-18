import { Picker, Text, View } from '@tarojs/components'

import type { ReadinessState, VerifiedWowObjectReference } from '@wow-mini/domain'

import { ActionButton } from './ActionButton'
import { GameObjectIcon } from './GameObjectIcon'
import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ProductionAssetImage } from './ProductionAsset'
import { ForgedPanel } from './ReconstructionPrimitives'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { reconstructionClass, reconstructionStyle } from './reconstruction-style'
import { styleSelectorClass } from './selector-markers'
import styles from './WorkbenchComponents.module.scss'

function workbenchStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(`workbench-${name}`)].filter(Boolean).join(' ')
}

export interface WorkbenchSpecSummaryProps {
  title: string
  sourceLabel: string
  contextDetail: string
  state: ReadinessState
  identity?: VerifiedWowObjectReference | null | undefined
  selectionLabels: readonly string[]
  selectionIndex: number
  selectionDisabled?: boolean | undefined
  scenarioLabels: readonly string[]
  scenarioIndex: number
  scenarioDisabled?: boolean | undefined
  onSelectionChange?: ((index: number) => void) | undefined
  onScenarioChange?: ((index: number) => void) | undefined
}

export function WorkbenchSpecSummary({
  title,
  sourceLabel,
  contextDetail,
  state,
  identity,
  selectionLabels,
  selectionIndex,
  selectionDisabled = false,
  scenarioLabels,
  scenarioIndex,
  scenarioDisabled = false,
  onSelectionChange,
  onScenarioChange,
}: WorkbenchSpecSummaryProps) {
  const safeSelectionLabels = selectionLabels.length ? [...selectionLabels] : ['暂无可用专精']
  const safeScenarioLabels = scenarioLabels.length ? [...scenarioLabels] : ['默认场景']

  return (
    <ForgedPanel
      className={reconstructionClass(
        reconstructionStyle('identitySummary'),
        reconstructionStyle('identitySummary-workbench'),
        workbenchStyle('specSummary'),
      )}
      contentInset={7}
      frameAssetId="builds-frame.overview"
      frameLayer="behind-content"
      frameSlotId="asset_slot.builds-frame-family"
      frameWidth={8}
      interactiveInset={8}
      owner="workbench-spec-summary"
      region="hero_card"
      tone={state === 'blocked' || state === 'error' ? 'blocked' : 'standard'}
    >
      <View
        className={reconstructionClass(reconstructionStyle('identityMedallion'), workbenchStyle('specMedallion'))}
        data-frame-content="true"
      >
        <ProductionAssetImage
          alt="专精徽章外壳"
          assetId="builds-specialization-medallion.shell"
          className={reconstructionStyle('workbenchIdentityMedallionShell')}
          slotId="asset_slot.builds-specialization-medallion"
        />
        <View className={reconstructionStyle('identityMedallionCore')}>
          <GameObjectIcon
            fallbackLabel="专精"
            object={identity}
            round
            size={54}
            slotId="asset_slot.workbench-specialization-object"
          />
        </View>
      </View>

      <View
        className={reconstructionClass(reconstructionStyle('identityCopy'), workbenchStyle('specCopy'))}
        data-frame-content="true"
      >
        <Text className={reconstructionClass(reconstructionStyle('identityTitle'), workbenchStyle('specTitle'))}>{title}</Text>
        <View className={reconstructionClass(reconstructionStyle('identityStatus'), workbenchStyle('specStatus'))}>
          <StatusVisual compact glyph="row" label={sourceLabel} state={state} variant="pill" />
        </View>
        <Picker
          disabled={scenarioDisabled || !onScenarioChange}
          mode="selector"
          range={safeScenarioLabels}
          value={Math.max(0, Math.min(scenarioIndex, safeScenarioLabels.length - 1))}
          onChange={(event) => onScenarioChange?.(Number(event.detail.value))}
        >
          <View
            aria-label={`切换模拟场景，当前${safeScenarioLabels[scenarioIndex] ?? safeScenarioLabels[0]}`}
            className={reconstructionClass(
              reconstructionStyle('workbenchScenarioControl'),
              workbenchStyle('scenarioControl'),
              (scenarioDisabled || !onScenarioChange) && workbenchStyle('controlDisabled'),
            )}
            data-disabled={scenarioDisabled || !onScenarioChange ? 'true' : 'false'}
            data-role="workbench-scenario-picker"
          >
            <Text className={reconstructionClass(reconstructionStyle('identitySubtitle'), workbenchStyle('scenarioLabel'))}>{contextDetail}</Text>
            <SystemGlyph
              assetId="utility-glyph-family.chevron-right"
              className={reconstructionStyle('workbenchScenarioChevron')}
              slotId="asset_slot.utility-glyph-family"
            />
          </View>
        </Picker>
      </View>

      <Picker
        disabled={selectionDisabled || !onSelectionChange}
        mode="selector"
        range={safeSelectionLabels}
        value={Math.max(0, Math.min(selectionIndex, safeSelectionLabels.length - 1))}
        onChange={(event) => onSelectionChange?.(Number(event.detail.value))}
      >
        <View
          aria-label={`切换职业专精，当前${title}`}
          className={reconstructionClass(
            reconstructionStyle('workbenchSelectionControl'),
            workbenchStyle('selectionControl'),
            (selectionDisabled || !onSelectionChange) && workbenchStyle('controlDisabled'),
          )}
          data-disabled={selectionDisabled || !onSelectionChange ? 'true' : 'false'}
          data-frame-content="true"
          data-role="workbench-specialization-picker"
        >
          <SystemGlyph
            assetId="utility-glyph-family.chevron-right"
            className={reconstructionStyle('identityChevron')}
            slotId="asset_slot.utility-glyph-family"
          />
        </View>
      </Picker>
    </ForgedPanel>
  )
}

export interface WorkbenchPrimaryAction {
  label: string
  disabled?: boolean | undefined
}

export interface WorkbenchReadinessPanelProps {
  statusLabel: string
  headline: string
  reasons: readonly string[]
  state: ReadinessState
  primaryAction: WorkbenchPrimaryAction
  onPrimary?: (() => void) | undefined
}

const readinessGlyph: Readonly<Record<ReadinessState, string>> = {
  loading: 'utility-glyph-family.runtime',
  empty: 'utility-glyph-family.warning',
  error: 'utility-glyph-family.warning',
  blocked: 'utility-glyph-family.warning',
  partial: 'utility-glyph-family.adjust',
  ready: 'utility-glyph-family.shield',
  stale: 'utility-glyph-family.records',
  source_reference: 'utility-glyph-family.source-link',
  unknown: 'utility-glyph-family.warning',
}

export function WorkbenchReadinessPanel({
  statusLabel,
  headline,
  reasons,
  state,
  primaryAction,
  onPrimary,
}: WorkbenchReadinessPanelProps) {
  const visibleReasons = (reasons.length ? reasons : ['输入状态暂不可用', '请重新读取当前工作台']).slice(0, 2)
  const emblemAssetId = state === 'blocked' || state === 'error' || state === 'empty'
    ? 'builds-workspace-medallion.blocked'
    : 'builds-workspace-medallion.default'

  return (
    <ForgedPanel
      className={reconstructionClass(reconstructionStyle('workbenchBlocker'), workbenchStyle('readinessPanel'))}
      contentInset={11}
      frameAssetId="builds-frame.workspace-gold"
      frameLayer="behind-content"
      frameSlotId="asset_slot.builds-frame-family"
      frameWidth={9}
      interactiveInset={12}
      owner="workbench-readiness-panel"
      region="warning_panel"
      tone={state === 'blocked' || state === 'error' ? 'blocked' : 'bright'}
    >
      <View
        className={reconstructionClass(reconstructionStyle('workbenchBlockerCopy'), workbenchStyle('readinessCopy'))}
        data-frame-content="true"
      >
        <View className={reconstructionStyle('workbenchBlockerTitleRow')}>
          <SystemGlyph
            assetId={readinessGlyph[state]}
            className={reconstructionStyle('workbenchBlockerLock')}
            slotId="asset_slot.utility-glyph-family"
          />
          <Text className={reconstructionStyle('workbenchBlockerEyebrow')}>{statusLabel}</Text>
        </View>
        <Text className={reconstructionStyle('workbenchBlockerHeadline')}>{headline}</Text>
        <View className={reconstructionStyle('workbenchBlockerReasons')}>
          {visibleReasons.map((reason, index) => (
            <View key={`${index}-${reason}`} className={reconstructionStyle('workbenchBlockerReason')} data-role="workbench-blocker-reason">
              <View className={reconstructionStyle('workbenchBlockerReasonDot')} data-state={state} />
              <Text className={reconstructionStyle('workbenchBlockerReasonText')}>{reason}</Text>
            </View>
          ))}
        </View>
        <ActionButton
          className={workbenchStyle('readinessAction')}
          disabled={primaryAction.disabled}
          iconPath={undefined}
          variant="primaryGold"
          onClick={onPrimary}
        >
          {primaryAction.label}
        </ActionButton>
      </View>
      <View
        className={reconstructionClass(reconstructionStyle('workbenchBlockerEmblem'), workbenchStyle('readinessEmblem'))}
        data-frame-content="true"
        data-slot="asset_slot.workbench-readiness-emblem"
      >
        <ProductionAssetGlyph
          assetId={emblemAssetId}
          className={reconstructionStyle('workbenchBlockerEmblemAsset')}
          fallbackAssetId={readinessGlyph[state]}
          fallbackSlotId="asset_slot.utility-glyph-family"
          slotId="asset_slot.workbench-readiness-emblem"
        />
        <SystemGlyph
          assetId={readinessGlyph[state]}
          className={reconstructionStyle('workbenchBlockerWarning')}
          slotId="asset_slot.utility-glyph-family"
        />
      </View>
    </ForgedPanel>
  )
}

export interface WorkbenchModuleCard {
  id: string
  title: string
  summary: string
  state: ReadinessState
  stateLabel?: string | undefined
  disabled?: boolean | undefined
}

export interface WorkbenchModuleDeckProps {
  modules: readonly WorkbenchModuleCard[]
  onModule?: ((module: WorkbenchModuleCard) => void) | undefined
}

const moduleAssets: Readonly<Record<string, {
  assetId: string
  fallbackAssetId: string
  toneClass: string
}>> = {
  talents: {
    assetId: 'builds-evidence-medallion.talents',
    fallbackAssetId: 'quick-action-talents-glyph.default',
    toneClass: 'workbenchModule-talent',
  },
  gear: {
    assetId: 'builds-evidence-medallion.gear',
    fallbackAssetId: 'quick-action-gear-glyph.default',
    toneClass: 'workbenchModule-gear',
  },
  simc: {
    assetId: 'builds-evidence-medallion.simc',
    fallbackAssetId: 'quick-action-simc-glyph.default',
    toneClass: 'workbenchModule-simc',
  },
  assistant: {
    assetId: 'builds-workspace-medallion.default',
    fallbackAssetId: 'utility-glyph-family.assistant',
    toneClass: 'workbenchModule-captain',
  },
}

export function WorkbenchModuleDeck({ modules, onModule }: WorkbenchModuleDeckProps) {
  return (
    <View
      className={reconstructionClass(reconstructionStyle('workbenchModuleGrid'), workbenchStyle('moduleGrid'))}
      data-owner="workbench-module-deck"
      data-region="module_cards_row"
      data-role="workbench-module-deck"
    >
      {modules.map((module) => {
        const asset = moduleAssets[module.id] ?? moduleAssets['assistant']
        if (!asset) return null
        const disabled = module.disabled || !onModule
        return (
          <ForgedPanel
            key={module.id}
            className={reconstructionClass(
              reconstructionStyle('workbenchModule'),
              reconstructionStyle(asset.toneClass),
              workbenchStyle('moduleCard'),
              workbenchStyle(module.id === 'talents'
                ? 'moduleTalent'
                : module.id === 'gear'
                  ? 'moduleGear'
                  : module.id === 'simc'
                    ? 'moduleSimc'
                    : 'moduleAssistant'),
            )}
            contentInset={4}
            frameAssetId="builds-frame.evidence-grid"
            frameLayer="behind-content"
            frameSlotId="asset_slot.builds-frame-family"
            frameWidth={6}
            interactiveInset={5}
            owner="workbench-module-card"
            region={`module_cards_row.${module.id}`}
            onClick={disabled ? undefined : () => onModule(module)}
          >
            <View
              aria-label={`${module.title}，${module.stateLabel ?? module.state}，${module.summary}`}
              className={reconstructionClass(
                reconstructionStyle('workbenchModuleContent'),
                workbenchStyle('moduleContent'),
                disabled && workbenchStyle('moduleDisabled'),
              )}
              data-disabled={disabled ? 'true' : 'false'}
              data-frame-content="true"
              data-module-id={module.id}
              data-state={module.state}
              data-role="workbench-module-card"
            >
              <View
                className={reconstructionClass(reconstructionStyle('workbenchModuleFlag'), workbenchStyle('moduleFlag'))}
                data-role="workbench-module-flag"
              >
                <SystemGlyph
                  assetId={asset.fallbackAssetId}
                  className={reconstructionStyle('workbenchModuleFlagGlyph')}
                  slotId="asset_slot.utility-glyph-family"
                />
              </View>
              <View
                className={reconstructionClass(reconstructionStyle('workbenchModuleSocket'), workbenchStyle('moduleSocket'))}
                data-slot="asset_slot.workbench-module-medallions"
              >
                <ProductionAssetGlyph
                  assetId={asset.assetId}
                  className={reconstructionStyle('workbenchModuleMedallion')}
                  fallbackAssetId={asset.fallbackAssetId}
                  fallbackSlotId="asset_slot.utility-glyph-family"
                  slotId="asset_slot.workbench-module-medallions"
                />
              </View>
              <Text className={reconstructionClass(reconstructionStyle('workbenchModuleTitle'), workbenchStyle('moduleTitle'))}>{module.title}</Text>
              <View className={workbenchStyle('moduleCopy')}>
                <Text className={workbenchStyle('moduleState')}>{module.stateLabel ?? module.state}</Text>
                <Text className={reconstructionClass(reconstructionStyle('workbenchModuleSummary'), workbenchStyle('moduleSummary'))}>
                  {module.summary}
                </Text>
              </View>
              <SystemGlyph
                assetId="utility-glyph-family.chevron-right"
                className={reconstructionStyle('workbenchModuleChevron')}
                slotId="asset_slot.utility-glyph-family"
              />
            </View>
          </ForgedPanel>
        )
      })}
    </View>
  )
}

export interface WorkbenchMenuActionProps {
  onClick?: (() => void) | undefined
}

export function WorkbenchMenuAction({ onClick }: WorkbenchMenuActionProps) {
  return (
    <View
      className={reconstructionClass(reconstructionStyle('workbenchMenu'), workbenchStyle('menu'))}
      data-role="workbench-menu-action"
    >
      <ActionButton ariaLabel="管理构筑模板" variant="ghost" onClick={onClick}>
        <SystemGlyph
          assetId="utility-glyph-family.menu"
          className={reconstructionStyle('workbenchMenuGlyph')}
          slotId="asset_slot.utility-glyph-family"
        />
      </ActionButton>
    </View>
  )
}
